class Scheduling:
    def schedule(self, work_item: dict) -> dict:
        return {'status': 'scheduled', 'work_item': dict(work_item)}
