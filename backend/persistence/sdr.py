"""SDR authorship enrichment without changing provider prompts or algorithms."""
from backend.sdr.storage import SdrStore

class PgSdrStore(SdrStore):
    def history(self,lead_id):
        data=super().history(lead_id)
        with self.reader.connect() as (c,_):
            rows=c.execute('SELECT o.id,p.display_name FROM outreach o LEFT JOIN profiles p ON p.id=o.updated_by WHERE o.lead_id=?',(lead_id,)).fetchall()
        names={row['id']:row['display_name'] for row in rows}
        for item in data['items']:item['actorName']=names.get(item['id']) or 'Autoria legada desconhecida'
        return data
