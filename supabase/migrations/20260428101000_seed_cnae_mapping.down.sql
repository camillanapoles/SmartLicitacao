-- Rollback DATA-CNAE-001 seed migration.
--
-- Removes ONLY the rows whose ``notes`` column matches the seed
-- marker.  Preserves any rows added/edited by admin operators after
-- the seed was applied (those rows have a different notes value or
-- have been touched by a CRUD update).

DELETE FROM public.cnae_setor_mapping
 WHERE notes = 'Seeded from legacy cnae_mapping.py 2026-04-28';
