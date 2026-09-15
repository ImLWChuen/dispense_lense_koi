from app.api.cases import get_diagnosis_engine
from app.schemas.case import CreateCaseRequest
from app.schemas.diagnosis import Observation

engine = get_diagnosis_engine()
request = CreateCaseRequest(
    defect_code="D01_TOO_LITTLE",
    description="Test",
    observations=[Observation(observation_type="deposit_size", value="undersized")]
)
domain_request = request.to_diagnosis_request()
case = engine.prepare_case(domain_request)
print("Case prepared:", case)
result = engine.diagnose(case)
print("Diagnosed:", result)
