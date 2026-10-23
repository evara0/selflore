CREATE TABLE app.card_import_batches (
 owner_id uuid NOT NULL REFERENCES app.users(id), batch_id uuid NOT NULL,
 digest char(64) NOT NULL, result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(owner_id,batch_id)
);
