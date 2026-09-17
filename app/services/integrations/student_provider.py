class StudentProvider:
    def find_by_cpf(self, cpf):
        raise NotImplementedError

class MockStudentProvider(StudentProvider):
    def find_by_cpf(self, cpf):
        return {'external_id': None, 'name': 'Integração externa ainda não configurada', 'cpf': cpf}
