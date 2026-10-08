CREATE TABLE app.review_units (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL, card_id uuid NOT NULL,
    card_kind text NOT NULL DEFAULT 'knowledge' CHECK(card_kind='knowledge'),
    cloze_index smallint NOT NULL CHECK(cloze_index BETWEEN 0 AND 99), is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(owner_id,id), UNIQUE(owner_id,id,card_id), UNIQUE(owner_id,card_id,cloze_index),
    FOREIGN KEY(owner_id,card_id,card_kind) REFERENCES app.cards(owner_id,id,kind)
);
CREATE INDEX review_units_card_idx ON app.review_units(owner_id,card_id);
CREATE TABLE app.review_states (
    owner_id uuid NOT NULL, unit_id uuid NOT NULL, PRIMARY KEY(owner_id,unit_id),
    state text NOT NULL DEFAULT 'new' CHECK(state IN ('new','learning','review','relearning')),
    due_at timestamptz NOT NULL, last_reviewed_at timestamptz,
    review_count integer NOT NULL DEFAULT 0 CHECK(review_count>=0), lapse_count integer NOT NULL DEFAULT 0 CHECK(lapse_count>=0),
    scheduler_payload jsonb NOT NULL CHECK(jsonb_typeof(scheduler_payload)='object'), scheduler_version varchar(80) NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK(version>=1), FOREIGN KEY(owner_id,unit_id) REFERENCES app.review_units(owner_id,id)
);
CREATE INDEX review_states_due_idx ON app.review_states(owner_id,state,due_at,unit_id);
CREATE TABLE app.review_logs (
    id uuid PRIMARY KEY, owner_id uuid NOT NULL, unit_id uuid NOT NULL, card_id uuid NOT NULL,
    request_id uuid NOT NULL, request_digest char(64) NOT NULL CHECK(request_digest ~ '^[0-9a-f]{64}$'),
    rating smallint NOT NULL CHECK(rating BETWEEN 1 AND 4), reviewed_at timestamptz NOT NULL,
    duration_ms integer NOT NULL CHECK(duration_ms BETWEEN 0 AND 3600000),
    content_revision integer NOT NULL CHECK(content_revision>=1), state_version_before integer NOT NULL CHECK(state_version_before>=1),
    scheduler_version varchar(80) NOT NULL, state_before jsonb NOT NULL, state_after jsonb NOT NULL,
    content_snapshot jsonb NOT NULL, response_payload jsonb NOT NULL,
    UNIQUE(owner_id,request_id), FOREIGN KEY(owner_id,unit_id,card_id) REFERENCES app.review_units(owner_id,id,card_id)
);
CREATE INDEX review_logs_date_idx ON app.review_logs(owner_id,reviewed_at DESC,id DESC);
