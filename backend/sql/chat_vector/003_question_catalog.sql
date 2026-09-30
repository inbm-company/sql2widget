-- Preserve catalog data while using the product's question terminology.
ALTER TABLE command_catalog RENAME TO question_catalog;
ALTER TABLE question_catalog RENAME COLUMN command TO question;
ALTER TABLE question_catalog RENAME COLUMN command_key TO question_key;
ALTER INDEX idx_command_catalog_scope RENAME TO idx_question_catalog_scope;
