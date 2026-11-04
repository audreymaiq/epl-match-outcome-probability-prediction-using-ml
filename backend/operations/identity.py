"""Explicitly link a provider ID to an existing canonical entity."""

from sqlalchemy import text
from utils.db_connector import DatabaseConnector
from utils.external_mapping import upsert_mapping

TABLES = {"team": "Teams", "league": "Leagues", "season": "Seasons", "match": "Matches",
          "player": "Players", "stadium": "Stadiums", "referee": "Referees"}


def link_entity(source, entity_type, external_id, internal_id, scope=""):
    if entity_type not in TABLES:
        raise ValueError("Unsupported entity type")
    with DatabaseConnector.session_scope() as session:
        row = session.execute(text(f'SELECT * FROM "{TABLES[entity_type]}" WHERE id=:id'), {"id": internal_id}).first()
        if row is None:
            raise ValueError("Canonical entity does not exist")
        if entity_type == "season" and str(row.league_id) != scope:
            raise ValueError("Season mappings require scope equal to the canonical league ID")
        upsert_mapping(str(external_id), internal_id, entity_type, source, session=session, scope=scope)
    return {"source": source, "entity": entity_type, "external_id": external_id, "internal_id": internal_id, "scope": scope}
