-- catalog.db — migration 0002 : rollup journalier des observations (compaction).
-- Écrite/lue UNIQUEMENT par l'outil de compaction + le merge ; le crawler l'ignore.
-- Une ligne = UN bucket (ed2k_hash, jour UTC), node-agnostique : agrégat de TOUTES les
-- observations de ce fichier ce jour-là, tous nœuds confondus. source_count et
-- complete_source_count sont NOT NULL dans file_observations → agrégats toujours définis.
-- filenames / node_ids : tableaux JSON CANONIQUES (distincts, triés). moyenne = sum / count
-- (non stockée — exacte, associativement combinable). Migration ADDITIVE : ne reconstruit
-- aucune table de 0001, ne touche donc pas à ses triggers.

CREATE TABLE file_observation_ranges (
    id INTEGER PRIMARY KEY,
    ed2k_hash TEXT NOT NULL REFERENCES files (ed2k_hash),
    bucket TEXT NOT NULL,
    filenames TEXT NOT NULL,
    node_ids TEXT NOT NULL,
    observation_count INTEGER NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    source_count_min INTEGER NOT NULL,
    source_count_max INTEGER NOT NULL,
    source_count_sum INTEGER NOT NULL,
    complete_source_count_min INTEGER NOT NULL,
    complete_source_count_max INTEGER NOT NULL,
    complete_source_count_sum INTEGER NOT NULL,
    CHECK (observation_count > 0),
    CHECK (first_observed_at <= last_observed_at),
    CHECK (LENGTH(bucket) = 10)
);

CREATE INDEX idx_file_observation_ranges_ed2k_hash
ON file_observation_ranges (ed2k_hash);

CREATE TRIGGER file_observation_ranges_no_update
BEFORE UPDATE ON file_observation_ranges
BEGIN
    SELECT RAISE(ABORT, 'file_observation_ranges est append-only');
END;

CREATE TRIGGER file_observation_ranges_no_delete
BEFORE DELETE ON file_observation_ranges
BEGIN
    SELECT RAISE(ABORT, 'file_observation_ranges est append-only');
END;
