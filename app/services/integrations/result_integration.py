class ResultIntegration:
    def send_result(self, correction):
        raise NotImplementedError

class NoOpResultIntegration(ResultIntegration):
    def send_result(self, correction):
        return {'status': 'pending', 'external_id': None}
