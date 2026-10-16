from trust_receipt.commitments import ValidationRegistryReadProbe


class _Call:
    def __init__(self, value):
        self._value = value

    def call(self):
        return self._value


class _Functions:
    def __init__(self, identity):
        self._identity = identity

    def getIdentityRegistry(self):
        return _Call(self._identity)

    def getAgentValidations(self, agent_id):
        assert agent_id == 10691
        return _Call([b"a" * 32])


class _Contract:
    def __init__(self, identity):
        self.functions = _Functions(identity)


class _Rpc:
    def __init__(self, identity):
        self.identity = identity
        self.code_checked = False

    def chain_id(self):
        return 11_155_111

    def contract_code(self, address):
        self.code_checked = bool(address)
        return b"code"

    def contract(self, address, abi):
        assert address and abi
        return _Contract(self.identity)


def test_probe_reports_real_interface_semantics_without_claiming_anchor_support() -> None:
    identity = "0x" + "11" * 20
    rpc = _Rpc(identity)
    result = ValidationRegistryReadProbe(
        rpc,
        validation_registry="0x" + "22" * 20,
        expected_identity_registry=identity,
    ).probe("11155111:10691")

    assert rpc.code_checked
    assert result.existing_request_count == 1
    assert result.supports_task_commitment_anchor is False
    assert "not a requester-owned" in result.limitation
