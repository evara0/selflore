-- Snapshot, normalize and verify under the migration transaction's locks.
LOCK TABLE app.topics, app.tags, app.card_topics, app.card_tags IN ACCESS EXCLUSIVE MODE;
CREATE FUNCTION app.normalize_tag_name(value text) RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
 SELECT btrim(normalize(value,NFKC), U&'\0009\000A\000B\000C\000D\001C\001D\001E\001F\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000')
$$;
CREATE TABLE app.legacy_tags AS TABLE app.tags;
CREATE TABLE app.legacy_card_tags AS TABLE app.card_tags;
CREATE TEMP TABLE tag_candidates ON COMMIT DROP AS
 SELECT owner_id,id,'tag'::text AS source_type,NULL::text AS kind,name,created_at,app.normalize_tag_name(name) AS normalized_name FROM app.tags
 UNION ALL SELECT owner_id,id,'topic',kind,name,created_at,app.normalize_tag_name(name) FROM app.topics;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM tag_candidates WHERE length(normalized_name) NOT BETWEEN 1 AND 80) THEN
  RAISE EXCEPTION 'invalid normalized legacy tag name';
 END IF;
END $$;
CREATE TEMP TABLE tag_winners ON COMMIT DROP AS
 SELECT DISTINCT ON (owner_id,normalized_name) owner_id,normalized_name,id,created_at,source_type
 FROM tag_candidates ORDER BY owner_id,normalized_name,(source_type='tag') DESC,created_at,id;
-- Topic UUIDs are globally unique among topics but may collide with existing tags.
UPDATE tag_winners w SET id=gen_random_uuid() WHERE w.source_type='topic'
 AND EXISTS(SELECT 1 FROM app.tags t WHERE t.id=w.id);
CREATE TABLE app.tag_aliases (
 owner_id uuid NOT NULL REFERENCES app.users(id), source_type text NOT NULL CHECK(source_type IN ('topic','tag')),
 old_id uuid NOT NULL, canonical_tag_id uuid, kind text CHECK(kind IN ('knowledge','opinion','reference')),
 original_name text NOT NULL, original_created_at timestamptz NOT NULL,
 PRIMARY KEY(owner_id,source_type,old_id),
 CHECK((source_type='topic')=(kind IS NOT NULL))
);
INSERT INTO app.tag_aliases SELECT c.owner_id,c.source_type,c.id,w.id,c.kind,c.name,c.created_at
 FROM tag_candidates c JOIN tag_winners w USING(owner_id,normalized_name);
DELETE FROM app.card_tags;
DELETE FROM app.tags;
ALTER TABLE app.tags ALTER COLUMN name TYPE varchar(80);
ALTER TABLE app.tags ADD COLUMN normalized_name text GENERATED ALWAYS AS (app.normalize_tag_name(name)) STORED;
ALTER TABLE app.tags ADD CONSTRAINT tags_normalized_name_check CHECK(length(normalized_name) BETWEEN 1 AND 80);
ALTER TABLE app.tags ADD CONSTRAINT tags_normalized_name_key UNIQUE(owner_id,normalized_name);
INSERT INTO app.tags(id,owner_id,name,created_at) SELECT id,owner_id,normalized_name,created_at FROM tag_winners;
ALTER TABLE app.tag_aliases ADD CONSTRAINT tag_aliases_target_fk FOREIGN KEY(owner_id,canonical_tag_id)
 REFERENCES app.tags(owner_id,id) ON DELETE SET NULL (canonical_tag_id);
CREATE TABLE app.card_tag_sources (
 owner_id uuid NOT NULL,card_id uuid NOT NULL,tag_id uuid NOT NULL,
 source_type text NOT NULL CHECK(source_type IN ('legacy_topic','legacy_tag','unified')),source_id uuid NOT NULL,
 PRIMARY KEY(owner_id,card_id,tag_id,source_type,source_id),
 FOREIGN KEY(owner_id,card_id) REFERENCES app.cards(owner_id,id),
 FOREIGN KEY(owner_id,tag_id) REFERENCES app.tags(owner_id,id)
);
INSERT INTO app.card_tag_sources
 SELECT r.owner_id,r.card_id,a.canonical_tag_id,'legacy_topic',r.topic_id
 FROM app.card_topics r JOIN app.tag_aliases a ON a.owner_id=r.owner_id AND a.old_id=r.topic_id AND a.source_type='topic'
 UNION ALL
 SELECT r.owner_id,r.card_id,a.canonical_tag_id,'legacy_tag',r.tag_id
 FROM app.legacy_card_tags r JOIN app.tag_aliases a ON a.owner_id=r.owner_id AND a.old_id=r.tag_id AND a.source_type='tag';
INSERT INTO app.card_tags SELECT DISTINCT owner_id,card_id,tag_id FROM app.card_tag_sources;
DO $$ BEGIN
 IF (SELECT count(*) FROM app.card_tag_sources) <> (SELECT count(*) FROM app.card_topics)+(SELECT count(*) FROM app.legacy_card_tags)
 OR EXISTS(SELECT 1 FROM app.card_tag_sources s LEFT JOIN app.card_tags r USING(owner_id,card_id,tag_id) WHERE r.card_id IS NULL)
 OR EXISTS(SELECT 1 FROM app.card_tags r LEFT JOIN app.card_tag_sources s USING(owner_id,card_id,tag_id) WHERE s.card_id IS NULL)
 OR EXISTS(SELECT 1 FROM app.card_tags GROUP BY owner_id,card_id HAVING count(*)>30) THEN
  RAISE EXCEPTION 'unified tag relationship verification failed';
 END IF;
END $$;
CREATE FUNCTION app.check_card_tag_limit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 -- Serialize concurrent relation writers, including direct SQL, on the parent.
 PERFORM 1 FROM app.cards WHERE owner_id=NEW.owner_id AND id=NEW.card_id FOR UPDATE;
 IF (SELECT count(*) FROM app.card_tags WHERE owner_id=NEW.owner_id AND card_id=NEW.card_id)>30 THEN
  RAISE EXCEPTION 'at most 30 tags per card' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER card_tag_limit AFTER INSERT OR UPDATE ON app.card_tags
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION app.check_card_tag_limit();
CREATE FUNCTION app.protect_tag_alias() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.owner_id,NEW.source_type,NEW.old_id,NEW.kind,NEW.original_name,NEW.original_created_at)
 IS DISTINCT FROM (OLD.owner_id,OLD.source_type,OLD.old_id,OLD.kind,OLD.original_name,OLD.original_created_at)
 OR (NEW.canonical_tag_id IS DISTINCT FROM OLD.canonical_tag_id AND NEW.canonical_tag_id IS NOT NULL) THEN
  RAISE EXCEPTION 'tag alias identity is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER tag_alias_identity BEFORE UPDATE ON app.tag_aliases FOR EACH ROW EXECUTE FUNCTION app.protect_tag_alias();
DO $$ BEGIN
 EXECUTE format('REVOKE INSERT,UPDATE,DELETE ON app.topics,app.card_topics FROM %I',replace(current_user,'_owner','_app'));
END $$;
