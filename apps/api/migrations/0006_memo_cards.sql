ALTER TABLE app.cards DROP CONSTRAINT cards_kind_check;
ALTER TABLE app.cards ADD CONSTRAINT cards_kind_check CHECK(kind IN ('knowledge','opinion','reference','memo'));
ALTER TABLE app.cards ADD COLUMN memo_format text;
ALTER TABLE app.cards ADD CONSTRAINT cards_memo_shape CHECK (
 (kind='memo' AND memo_format IS NOT NULL AND memo_format IN ('note','checklist') AND form IS NULL
  AND question_md IS NULL AND answer_md IS NULL AND note_md IS NULL)
 OR (kind<>'memo' AND memo_format IS NULL));
ALTER TABLE app.cards DROP CONSTRAINT cards_content_shape;
ALTER TABLE app.cards ADD CONSTRAINT cards_content_shape CHECK (
 (kind='knowledge' AND note_md IS NULL AND form IS NOT NULL AND form='qa'
  AND question_md IS NOT NULL AND length(trim(question_md))>0 AND answer_md IS NOT NULL
  AND length(trim(answer_md))>0 AND body_md IS NULL)
 OR (kind='knowledge' AND note_md IS NULL AND form IS NOT NULL AND form='cloze'
  AND body_md IS NOT NULL AND length(trim(body_md))>0 AND question_md IS NULL AND answer_md IS NULL)
 OR (kind='opinion' AND note_md IS NULL AND form IS NULL AND body_md IS NOT NULL
  AND length(trim(body_md))>0 AND question_md IS NULL AND answer_md IS NULL)
 OR (kind IN ('reference','memo') AND form IS NULL AND question_md IS NULL AND answer_md IS NULL));

CREATE TABLE app.memo_items (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, memo_card_id uuid NOT NULL,
 card_kind text NOT NULL DEFAULT 'memo' CHECK(card_kind='memo'),
 text varchar(2000) NOT NULL CHECK(length(trim(text))>0),
 position smallint NOT NULL CHECK(position BETWEEN 0 AND 199),
 is_completed boolean NOT NULL DEFAULT false, completed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_id,memo_card_id,id),
 UNIQUE(owner_id,memo_card_id,position) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(owner_id,memo_card_id,card_kind) REFERENCES app.cards(owner_id,id,kind),
 CHECK(is_completed=(completed_at IS NOT NULL)));
CREATE INDEX memo_items_open_idx ON app.memo_items(owner_id,is_completed,memo_card_id,position);
CREATE TABLE app.memo_item_links (
 owner_id uuid NOT NULL, memo_card_id uuid NOT NULL, item_id uuid NOT NULL, target_card_id uuid NOT NULL,
 PRIMARY KEY(owner_id,item_id,target_card_id), CHECK(memo_card_id<>target_card_id),
 FOREIGN KEY(owner_id,memo_card_id,item_id) REFERENCES app.memo_items(owner_id,memo_card_id,id) ON DELETE CASCADE,
 FOREIGN KEY(owner_id,target_card_id) REFERENCES app.cards(owner_id,id));
CREATE INDEX memo_item_links_target_idx ON app.memo_item_links(owner_id,target_card_id,memo_card_id);
CREATE VIEW app.all_card_links AS
 SELECT owner_id,source_card_id,target_card_id,origin,NULL::uuid AS item_id FROM app.card_links
 UNION ALL SELECT owner_id,memo_card_id,target_card_id,'item',item_id FROM app.memo_item_links;

CREATE FUNCTION app.protect_memo_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='cards' THEN
  IF (NEW.kind,NEW.form,NEW.memo_format) IS DISTINCT FROM (OLD.kind,OLD.form,OLD.memo_format) THEN
   RAISE EXCEPTION 'card type and form are immutable' USING ERRCODE='23514';
  END IF;
 ELSE
  IF (NEW.id,NEW.owner_id,NEW.memo_card_id) IS DISTINCT FROM (OLD.id,OLD.owner_id,OLD.memo_card_id) THEN
   RAISE EXCEPTION 'memo item identity is immutable' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER cards_memo_identity BEFORE UPDATE ON app.cards FOR EACH ROW EXECUTE FUNCTION app.protect_memo_identity();
CREATE TRIGGER memo_items_identity BEFORE UPDATE ON app.memo_items FOR EACH ROW EXECUTE FUNCTION app.protect_memo_identity();

CREATE FUNCTION app.check_memo_material() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target uuid; actor uuid; mode text; n integer;
BEGIN
 IF TG_TABLE_NAME='cards' THEN target:=NEW.id; actor:=NEW.owner_id;
 ELSIF TG_OP='DELETE' THEN target:=OLD.memo_card_id; actor:=OLD.owner_id;
 ELSE target:=NEW.memo_card_id; actor:=NEW.owner_id; END IF;
 SELECT memo_format INTO mode FROM app.cards WHERE owner_id=actor AND id=target FOR UPDATE;
 SELECT count(*) INTO n FROM app.memo_items WHERE owner_id=actor AND memo_card_id=target;
 IF (mode='checklist' AND (n<1 OR n>200)) OR (mode IS DISTINCT FROM 'checklist' AND n>0) THEN
  RAISE EXCEPTION 'checklist requires 1 to 200 items; note has no items' USING ERRCODE='23514';
 END IF;
 IF EXISTS(SELECT 1 FROM app.memo_item_links WHERE owner_id=actor AND memo_card_id=target GROUP BY item_id HAVING count(*)>20) THEN
  RAISE EXCEPTION 'at most 20 links per item' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER memo_card_material AFTER INSERT OR UPDATE ON app.cards DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION app.check_memo_material();
CREATE CONSTRAINT TRIGGER memo_item_material AFTER INSERT OR UPDATE OR DELETE ON app.memo_items DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION app.check_memo_material();
CREATE CONSTRAINT TRIGGER memo_link_material AFTER INSERT OR UPDATE OR DELETE ON app.memo_item_links DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION app.check_memo_material();

ALTER TABLE app.activity_events DROP CONSTRAINT activity_events_event_kind_check;
ALTER TABLE app.activity_events DROP CONSTRAINT activity_events_check;
ALTER TABLE app.activity_events ADD CONSTRAINT activity_events_event_kind_check CHECK(event_kind IN (
 'card_created','card_updated','card_organized','reviewed','collection_created','collection_updated',
 'memo_created','memo_updated','memo_organized','memo_item_completed','memo_item_reopened'));
ALTER TABLE app.activity_events ADD CONSTRAINT activity_events_check CHECK(
 (event_kind IN ('collection_created','collection_updated') AND collection_id IS NOT NULL AND card_id IS NULL)
 OR (event_kind IN ('card_created','card_updated','card_organized','reviewed','memo_created','memo_updated',
 'memo_organized','memo_item_completed','memo_item_reopened') AND card_id IS NOT NULL AND collection_id IS NULL));
