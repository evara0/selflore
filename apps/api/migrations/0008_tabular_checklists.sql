ALTER TABLE app.cards
 ADD COLUMN memo_columns text[] NOT NULL DEFAULT ARRAY['条目','字段 2','字段 3'],
 ADD COLUMN memo_column_count smallint NOT NULL DEFAULT 1,
 ADD CONSTRAINT cards_memo_columns_check CHECK (
  array_ndims(memo_columns)=1 AND array_lower(memo_columns,1)=1 AND cardinality(memo_columns)=3
  AND array_position(memo_columns,NULL) IS NULL
  AND length(trim(memo_columns[1])) BETWEEN 1 AND 40
  AND length(trim(memo_columns[2])) BETWEEN 1 AND 40
  AND length(trim(memo_columns[3])) BETWEEN 1 AND 40
  AND memo_column_count BETWEEN 1 AND 3);
ALTER TABLE app.memo_items
 ADD COLUMN extra_values text[] NOT NULL DEFAULT ARRAY['',''],
 ADD CONSTRAINT memo_items_extra_values_check CHECK (
  array_ndims(extra_values)=1 AND array_lower(extra_values,1)=1 AND cardinality(extra_values)=2
  AND array_position(extra_values,NULL) IS NULL
  AND length(extra_values[1])<=2000 AND length(extra_values[2])<=2000);
