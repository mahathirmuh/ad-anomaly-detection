
                MATCH (u:User)-[r:MODIFIED_GPO]->(gpo:GPO)
                RETURN u.username, count(r) as gpo_changes, 
                       collect(DISTINCT gpo.gponame) as modified_gpos
                ORDER BY gpo_changes DESC
            