ALTER TABLE app.cards DROP CONSTRAINT cards_kind_check;
ALTER TABLE app.cards ADD CONSTRAINT cards_kind_check CHECK(kind IN ('knowledge','opinion','reference'));
ALTER TABLE app.topics DROP CONSTRAINT topics_kind_check;
ALTER TABLE app.topics ADD CONSTRAINT topics_kind_check CHECK(kind IN ('knowledge','opinion','reference'));
CREATE UNIQUE INDEX card_topics_reference_idx ON app.card_topics(owner_id,card_id) WHERE card_kind='reference';
ALTER TABLE app.cards ADD COLUMN note_md text CHECK(octet_length(note_md)<=65536);
ALTER TABLE app.cards ADD COLUMN source_author varchar(200);
ALTER TABLE app.cards ADD COLUMN source_publisher varchar(200);
ALTER TABLE app.cards ADD COLUMN source_platform varchar(80);
ALTER TABLE app.cards ADD COLUMN source_published_on date;
ALTER TABLE app.cards DROP CONSTRAINT cards_content_shape;
ALTER TABLE app.cards ADD CONSTRAINT cards_content_shape CHECK (
 (kind='knowledge' AND note_md IS NULL AND form='qa' AND form IS NOT NULL
  AND question_md IS NOT NULL AND length(trim(question_md))>0 AND answer_md IS NOT NULL
  AND length(trim(answer_md))>0 AND body_md IS NULL)
 OR (kind='knowledge' AND note_md IS NULL AND form='cloze' AND form IS NOT NULL
  AND body_md IS NOT NULL AND length(trim(body_md))>0 AND question_md IS NULL AND answer_md IS NULL)
 OR (kind='opinion' AND note_md IS NULL AND form IS NULL AND body_md IS NOT NULL
  AND length(trim(body_md))>0 AND question_md IS NULL AND answer_md IS NULL)
 OR (kind='reference' AND form IS NULL AND question_md IS NULL AND answer_md IS NULL)
);
CREATE TABLE app.attachments (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES app.users(id),
 storage_backend text NOT NULL DEFAULT 'local' CHECK(storage_backend='local'),
 original_key text, thumbnail_key text,
 original_bytes bigint CHECK(original_bytes>0), thumbnail_bytes bigint CHECK(thumbnail_bytes>0),
 original_sha256 char(64), thumbnail_sha256 char(64), mime_type text,
 width integer CHECK(width>0), height integer CHECK(height>0),
 status text NOT NULL CHECK(status IN ('uploading','ready','failed')),
 client_request_id uuid NOT NULL, request_sha256 char(64) NOT NULL CHECK(request_sha256 ~ '^[0-9a-f]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_id,id), UNIQUE(owner_id,client_request_id),
 CHECK(status<>'ready' OR (original_key IS NOT NULL AND thumbnail_key IS NOT NULL
  AND original_bytes IS NOT NULL AND thumbnail_bytes IS NOT NULL AND width IS NOT NULL AND height IS NOT NULL
  AND original_sha256 IS NOT NULL AND original_sha256 ~ '^[0-9a-f]{64}$'
  AND thumbnail_sha256 IS NOT NULL AND thumbnail_sha256 ~ '^[0-9a-f]{64}$'
  AND original_sha256=request_sha256 AND mime_type IS NOT NULL AND mime_type IN ('image/jpeg','image/png','image/webp')))
);
CREATE INDEX attachments_owner_status_idx ON app.attachments(owner_id,status,created_at);
CREATE TABLE app.card_attachments (
 owner_id uuid NOT NULL, card_id uuid NOT NULL, card_kind text NOT NULL DEFAULT 'reference' CHECK(card_kind='reference'),
 attachment_id uuid NOT NULL, position smallint NOT NULL CHECK(position>=0 AND position<10),
 caption varchar(2000) NOT NULL DEFAULT '', alt_text varchar(2000) NOT NULL DEFAULT '', creator_name varchar(200),
 PRIMARY KEY(owner_id,card_id,attachment_id),
 UNIQUE(owner_id,card_id,position) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(owner_id,card_id,card_kind) REFERENCES app.cards(owner_id,id,kind),
 FOREIGN KEY(owner_id,attachment_id) REFERENCES app.attachments(owner_id,id)
);
CREATE INDEX card_attachments_attachment_idx ON app.card_attachments(owner_id,attachment_id);
CREATE FUNCTION app.protect_card_attachment_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.owner_id,NEW.card_id,NEW.attachment_id) IS DISTINCT FROM (OLD.owner_id,OLD.card_id,OLD.attachment_id) THEN
  RAISE EXCEPTION 'attachment identity must be replaced transactionally' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER card_attachments_identity BEFORE UPDATE ON app.card_attachments
 FOR EACH ROW EXECUTE FUNCTION app.protect_card_attachment_identity();
CREATE FUNCTION app.check_reference_material() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target uuid; actor uuid;
BEGIN
 IF TG_TABLE_NAME='cards' THEN target:=NEW.id; actor:=NEW.owner_id;
 ELSE
  IF TG_OP='DELETE' THEN target:=OLD.card_id; actor:=OLD.owner_id;
  ELSE target:=NEW.card_id; actor:=NEW.owner_id; END IF;
 END IF;
 PERFORM 1 FROM app.cards WHERE id=target AND owner_id=actor FOR UPDATE;
 IF EXISTS(SELECT 1 FROM app.cards c WHERE c.id=target AND c.owner_id=actor AND c.kind='reference'
   AND coalesce(length(trim(c.body_md)),0)=0
   AND NOT EXISTS(SELECT 1 FROM app.card_attachments ca JOIN app.attachments a
    ON a.owner_id=ca.owner_id AND a.id=ca.attachment_id
    WHERE ca.owner_id=actor AND ca.card_id=target AND a.status='ready')) THEN
  RAISE EXCEPTION 'reference requires original material' USING ERRCODE='23514';
 END IF;
 IF EXISTS(SELECT 1 FROM app.card_attachments ca JOIN app.attachments a
   ON a.owner_id=ca.owner_id AND a.id=ca.attachment_id
   WHERE ca.owner_id=actor AND ca.card_id=target AND a.status<>'ready') THEN
  RAISE EXCEPTION 'reference requires ready attachment' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER cards_reference_material AFTER INSERT OR UPDATE ON app.cards
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION app.check_reference_material();
CREATE CONSTRAINT TRIGGER card_attachments_material AFTER INSERT OR UPDATE OR DELETE ON app.card_attachments
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION app.check_reference_material();
CREATE FUNCTION app.protect_ready_attachment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.status='ready' AND NEW IS DISTINCT FROM OLD THEN
  RAISE EXCEPTION 'ready attachments are immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER attachments_immutable BEFORE UPDATE ON app.attachments
 FOR EACH ROW EXECUTE FUNCTION app.protect_ready_attachment();
