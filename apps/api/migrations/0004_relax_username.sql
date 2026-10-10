ALTER TABLE app.users DROP CONSTRAINT users_username_check;
ALTER TABLE app.users ADD CONSTRAINT users_username_check
    CHECK (char_length(username) BETWEEN 3 AND 32
        AND username COLLATE "C" !~ '[^a-z0-9_一-鿿-]');
