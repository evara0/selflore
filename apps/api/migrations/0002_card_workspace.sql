DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace
               WHERE e.extname='pg_trgm' AND n.nspname<>'public') THEN
        RAISE EXCEPTION 'pg_trgm must be installed in public; will not relocate existing extension';
    END IF;
END $$;
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;

CREATE TABLE app.user_profiles (
    user_id uuid PRIMARY KEY REFERENCES app.users(id),
    display_name varchar(80) NOT NULL CHECK (length(trim(display_name))>0),
    bio text NOT NULL DEFAULT '' CHECK (octet_length(bio)<=8192),
    avatar_color text NOT NULL DEFAULT 'sage' CHECK (avatar_color IN ('sage','clay','ink')),
    interests text[] NOT NULL DEFAULT '{}' CHECK (cardinality(interests)<=8),
    timezone varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
    daily_new_limit smallint NOT NULL DEFAULT 20 CHECK (daily_new_limit BETWEEN 0 AND 100),
    daily_review_goal smallint NOT NULL DEFAULT 20 CHECK (daily_review_goal BETWEEN 1 AND 1000),
    revision integer NOT NULL DEFAULT 1 CHECK (revision>=1),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO app.user_profiles(user_id,display_name) SELECT id,username FROM app.users;

CREATE TABLE app.cards (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES app.users(id),
    code varchar(48) NOT NULL, kind text NOT NULL CHECK (kind IN ('knowledge','opinion')),
    form text CHECK (form IN ('qa','cloze')), title varchar(200) NOT NULL CHECK (length(trim(title))>0),
    question_md text CHECK (octet_length(question_md)<=65536),
    answer_md text CHECK (octet_length(answer_md)<=65536),
    body_md text CHECK (octet_length(body_md)<=65536),
    source_title varchar(200), source_url varchar(2048), source_locator varchar(200),
    processing_state text NOT NULL DEFAULT 'inbox' CHECK (processing_state IN ('inbox','organized')),
    lifecycle text NOT NULL DEFAULT 'active' CHECK (lifecycle IN ('active','archived','trashed')),
    trashed_at timestamptz, is_bookmarked boolean NOT NULL DEFAULT false,
    search_text text NOT NULL, revision integer NOT NULL DEFAULT 1 CHECK (revision>=1),
    client_request_id uuid NOT NULL, creation_request_digest char(64) NOT NULL CHECK (creation_request_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_id,id), UNIQUE(owner_id,id,kind), UNIQUE(owner_id,code), UNIQUE(owner_id,client_request_id),
    CHECK ((lifecycle='trashed')=(trashed_at IS NOT NULL)),
    CONSTRAINT cards_content_shape CHECK (
      (kind='knowledge' AND form IS NOT NULL AND form='qa' AND question_md IS NOT NULL AND length(trim(question_md))>0
       AND answer_md IS NOT NULL AND length(trim(answer_md))>0 AND body_md IS NULL)
      OR (kind='knowledge' AND form IS NOT NULL AND form='cloze' AND body_md IS NOT NULL AND length(trim(body_md))>0
          AND question_md IS NULL AND answer_md IS NULL)
      OR (kind='opinion' AND form IS NULL AND body_md IS NOT NULL AND length(trim(body_md))>0
          AND question_md IS NULL AND answer_md IS NULL)
    )
);
CREATE INDEX cards_owner_updated_idx ON app.cards(owner_id,kind,lifecycle,updated_at DESC,id DESC);
CREATE INDEX cards_processing_idx ON app.cards(owner_id,processing_state,updated_at DESC);
CREATE INDEX cards_bookmarked_idx ON app.cards(owner_id,updated_at DESC) WHERE is_bookmarked AND lifecycle='active';
CREATE INDEX cards_search_idx ON app.cards USING gin(search_text public.gin_trgm_ops);

CREATE TABLE app.topics (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES app.users(id),
    kind text NOT NULL CHECK (kind IN ('knowledge','opinion')),
    name varchar(80) NOT NULL CHECK (length(trim(name))>0), position integer NOT NULL DEFAULT 0 CHECK (position>=0),
    created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(owner_id,id,kind), UNIQUE(owner_id,kind,name)
);
CREATE TABLE app.card_topics (
    owner_id uuid NOT NULL, card_id uuid NOT NULL, topic_id uuid NOT NULL, card_kind text NOT NULL,
    PRIMARY KEY(owner_id,card_id,topic_id),
    FOREIGN KEY(owner_id,card_id,card_kind) REFERENCES app.cards(owner_id,id,kind),
    FOREIGN KEY(owner_id,topic_id,card_kind) REFERENCES app.topics(owner_id,id,kind)
);
CREATE UNIQUE INDEX card_topics_knowledge_idx ON app.card_topics(owner_id,card_id) WHERE card_kind='knowledge';
CREATE INDEX card_topics_lookup_idx ON app.card_topics(owner_id,topic_id,card_id);
CREATE TABLE app.tags (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES app.users(id),
    name varchar(32) NOT NULL CHECK (length(trim(name))>0), created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_id,id), UNIQUE(owner_id,name)
);
CREATE TABLE app.card_tags (
    owner_id uuid NOT NULL, card_id uuid NOT NULL, tag_id uuid NOT NULL, PRIMARY KEY(owner_id,card_id,tag_id),
    FOREIGN KEY(owner_id,card_id) REFERENCES app.cards(owner_id,id),
    FOREIGN KEY(owner_id,tag_id) REFERENCES app.tags(owner_id,id)
);
CREATE INDEX card_tags_lookup_idx ON app.card_tags(owner_id,tag_id,card_id);
CREATE TABLE app.card_links (
    owner_id uuid NOT NULL, source_card_id uuid NOT NULL, target_card_id uuid NOT NULL,
    origin text NOT NULL CHECK (origin IN ('inline','manual')), created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(owner_id,source_card_id,target_card_id,origin), CHECK(source_card_id<>target_card_id),
    FOREIGN KEY(owner_id,source_card_id) REFERENCES app.cards(owner_id,id),
    FOREIGN KEY(owner_id,target_card_id) REFERENCES app.cards(owner_id,id)
);
CREATE INDEX card_links_backlinks_idx ON app.card_links(owner_id,target_card_id,source_card_id);

CREATE TABLE app.collections (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES app.users(id),
    title varchar(200) NOT NULL CHECK (length(trim(title))>0), description_md text NOT NULL DEFAULT '' CHECK (octet_length(description_md)<=65536),
    cover_style text NOT NULL DEFAULT 'curve' CHECK (cover_style IN ('curve','lines','radial')),
    cover_color text NOT NULL DEFAULT 'sage' CHECK (cover_color IN ('sage','clay')),
    is_favorite boolean NOT NULL DEFAULT false, is_pinned boolean NOT NULL DEFAULT false,
    lifecycle text NOT NULL DEFAULT 'active' CHECK (lifecycle IN ('active','trashed')), trashed_at timestamptz,
    revision integer NOT NULL DEFAULT 1 CHECK(revision>=1), client_request_id uuid NOT NULL,
    creation_request_digest char(64) NOT NULL CHECK(creation_request_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_id,id), UNIQUE(owner_id,client_request_id), CHECK((lifecycle='trashed')=(trashed_at IS NOT NULL))
);
CREATE INDEX collections_updated_idx ON app.collections(owner_id,lifecycle,updated_at DESC,id DESC);
CREATE INDEX collections_pinned_idx ON app.collections(owner_id,updated_at DESC) WHERE is_pinned AND lifecycle='active';
CREATE TABLE app.collection_items (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL, collection_id uuid NOT NULL, card_id uuid NOT NULL,
    position integer NOT NULL CHECK(position>=0), created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_id,collection_id,card_id), UNIQUE(owner_id,collection_id,position) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(owner_id,collection_id) REFERENCES app.collections(owner_id,id),
    FOREIGN KEY(owner_id,card_id) REFERENCES app.cards(owner_id,id)
);
CREATE INDEX collection_items_card_idx ON app.collection_items(owner_id,card_id);
CREATE TABLE app.activity_events (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES app.users(id), card_id uuid, collection_id uuid,
    event_kind text NOT NULL CHECK(event_kind IN ('card_created','card_updated','card_organized','reviewed','collection_created','collection_updated')),
    entity_title varchar(200) NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(owner_id,card_id) REFERENCES app.cards(owner_id,id),
    FOREIGN KEY(owner_id,collection_id) REFERENCES app.collections(owner_id,id),
    CHECK ((event_kind IN ('card_created','card_updated','card_organized','reviewed') AND card_id IS NOT NULL AND collection_id IS NULL)
        OR (event_kind IN ('collection_created','collection_updated') AND collection_id IS NOT NULL AND card_id IS NULL))
);
CREATE INDEX activity_events_date_idx ON app.activity_events(owner_id,occurred_at DESC,id DESC);
