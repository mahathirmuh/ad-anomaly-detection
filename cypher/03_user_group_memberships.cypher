
                MATCH (u:User)-[:MEMBER_OF]->(g:Group)
                RETURN u.username, collect(g.groupname) as groups
                ORDER BY size(groups) DESC
                LIMIT 50
            