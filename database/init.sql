CREATE EXTENSION IF NOT EXISTS vector;

CREATE SEQUENCE IF NOT EXISTS ingredients_id_seq;

CREATE TABLE IF NOT EXISTS recipes (
    id INT NOT NULL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    steps JSONB NOT NULL DEFAULT '[]',
    source TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INT NOT NULL PRIMARY KEY DEFAULT nextval('ingredients_id_seq'),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE
);

ALTER TABLE ingredients
    ALTER COLUMN id SET DEFAULT nextval('ingredients_id_seq');
ALTER SEQUENCE ingredients_id_seq OWNED BY ingredients.id;
SELECT setval(
    'ingredients_id_seq',
    GREATEST(COALESCE((SELECT MAX(id) FROM ingredients), 0) + 1, 1),
    FALSE
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id BIGINT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id BIGINT NOT NULL REFERENCES ingredients(id),
    quantity NUMERIC,
    unit TEXT,
    PRIMARY KEY (recipe_id, ingredient_id)
);

CREATE SEQUENCE IF NOT EXISTS inventory_id_seq;

CREATE TABLE IF NOT EXISTS inventory (
    id INT NOT NULL PRIMARY KEY DEFAULT nextval('inventory_id_seq'),
    ingredient_id BIGINT NOT NULL REFERENCES ingredients(id),
    quantity NUMERIC,
    unit TEXT,
    maturity TEXT,
    confidence NUMERIC CHECK (confidence BETWEEN 0 AND 1),
    needs_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE inventory
    ALTER COLUMN id SET DEFAULT nextval('inventory_id_seq');
ALTER SEQUENCE inventory_id_seq OWNED BY inventory.id;
SELECT setval(
    'inventory_id_seq',
    GREATEST(COALESCE((SELECT MAX(id) FROM inventory), 0) + 1, 1),
    FALSE
);
CREATE UNIQUE INDEX IF NOT EXISTS inventory_ingredient_id_idx
    ON inventory (ingredient_id);

CREATE TABLE IF NOT EXISTS recipe_embeddings (
    recipe_id BIGINT PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);