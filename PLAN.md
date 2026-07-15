# PLAN — SampleOrderSystem 구현 계획 (Phase 기반)

`PRD.md`(Project.pdf Chapter 01/02 기반)의 전체 기능 명세를 만족하는 콘솔 애플리케이션을 구현한다. 네 개의 PoC(`ConsoleMVC`, `DataPersistence`, `DataMonitor`, `DummyDataGenerator`)에서 검증한 패턴을 이 리포에 새로 이식한다(파일 시스템 레벨 import 없음). 모든 산출물은 이 디렉토리(`SampleOrderSystem/`) 내부에만 위치한다.

개발은 아래 Phase 순서대로 진행한다. 각 Phase는 이전 Phase 위에 누적되며, Phase마다 자체적으로 `pytest` 전체 통과 상태를 유지한다(다음 Phase로 넘어가기 전에 그린 상태 확인). `actioner`가 Phase 단위로 구현하고, `tester`가 해당 Phase의 완료 기준을 검증한 뒤 다음 Phase로 진행한다.

## Phase별 PoC 참조 요약

| Phase | 주로 참조하는 PoC | 참조 방식 |
|---|---|---|
| 1. 스캐폴딩+영속성 | `DataPersistence` | 인터페이스/스키마/테스트 케이스를 그대로 이식(재작성) |
| 2. 시료 관리 | `ConsoleMVC` | model/view/controller 3계층 분리 패턴, 입력/출력 주입 패턴 이식 |
| 3. 주문 접수+메인메뉴 | `ConsoleMVC` | 메인 루프 구조 이식; `DummyDataGenerator` | 상태값 문자열 대조만 |
| 4. 승인/거절+생산큐 | — (PRD 고유 로직) | `DummyDataGenerator`의 상태값 문자열과 일치 여부만 대조 |
| 5. 생산 라인 | `DataMonitor` | 무캐시 재로드 원칙, 표 렌더링 패턴 참고 |
| 6. 출고 처리 | `ConsoleMVC` | 상태 변경 흐름 구조만 참고(신규 저장 로직 없음) |
| 7. 모니터링 | `DataMonitor`, `DummyDataGenerator` | 읽기 전용/재로드 원칙 이식; 더미 데이터로 포맷 호환성 수동 확인 |
| 8. 통합 마감 | 없음(검증만) | 단독 실행 가능성 grep 재확인 |

**공통 원칙**: 모든 "참조"는 해당 PoC의 소스 파일을 열어 인터페이스/패턴/원칙을 확인한 뒤 `SampleOrderSystem` 안에 **새로 작성**하는 것이며, 코드를 그대로 복사하거나 import하는 것이 아니다(위 "단독 실행 가능성" 절 참조).

## 0. 기술 스택 / 실행 방법 (전체 공통)

- **언어**: Python (3.10+)
- **테스트**: `pytest`
- **의존성**: 외부 런타임 의존성 없음(표준 라이브러리만 사용). 개발 의존성은 `requirements-dev.txt`에 `pytest` 명시.
- **실행**: `python -m sampleordersystem` (콘솔 메인 메뉴 실행, 최초 실행 시 `data/samples.json`, `data/orders.json`이 없으면 빈 상태로 시작)
- **테스트 실행**: `pytest` (디렉토리 루트에서, `pyproject.toml`의 `pythonpath = ["src"]`로 수동 PYTHONPATH 불필요)

## 도메인 모델 (PRD 그대로, 전체 Phase 공통 참조)

**Sample**: `id`, `name`, `avg_production_time`, `yield_rate`, `stock`

**Order**: `id`, `sample_id`, `customer_name`, `quantity`, `status` ∈ {`RESERVED`, `REJECTED`, `PRODUCING`, `CONFIRMED`, `RELEASED`}

상태 전이:
```
RESERVED --거절--> REJECTED
RESERVED --승인, 재고충분--> CONFIRMED --출고--> RELEASED
RESERVED --승인, 재고부족--> PRODUCING --생산완료(자동)--> CONFIRMED --출고--> RELEASED
```

생산 큐 계산식 (PRD 그대로, 순서 고정):
- 부족분 = 주문 수량 − 현재 재고
- 실 생산량 = `ceil(부족분 / 수율)`
- 총 생산 시간 = 평균 생산시간 × 실 생산량

의존 방향은 `ConsoleMVC`와 동일하게 `view` → `controller` → `model`. `persistence`는 `model`이 사용하되 콘솔 I/O를 모른다.

## 단독 실행 가능성 (하드 요구사항)

`SampleOrderSystem`은 다른 네 개 PoC 디렉토리와 별도의 public 저장소로 제출된다(루트 `CLAUDE.md` 참조). 따라서:

- **파일 시스템 레벨 import 금지**: 어떤 소스 파일에서도 `../ConsoleMVC`, `../DataPersistence`, `../DataMonitor`, `../DummyDataGenerator` 등 형제 디렉토리를 가리키는 `sys.path` 조작, 상대 경로 import, `PYTHONPATH` 의존이 있어서는 안 된다. 각 PoC에서 검증한 **패턴만 참고해 이 디렉토리 안에 새 코드로 다시 작성**한다(코드 복사/재작성 — import 아님).
- **의존성 자기완결**: `requirements-dev.txt`, `pyproject.toml`, `data/` 등 실행에 필요한 모든 것은 `SampleOrderSystem/` 내부에만 존재해야 한다. 이 디렉토리 하나만 별도로 clone해도 `pip install -r requirements-dev.txt` + `pytest` + `python -m sampleordersystem`이 그대로 동작해야 한다.
- **검증 방법**: 각 Phase의 `tester` 검증 시, 가능하면 `SampleOrderSystem/` 디렉토리만 놓고(다른 네 PoC 디렉토리가 없다고 가정하고) `grep -rn "ConsoleMVC\|DataPersistence\|DataMonitor\|DummyDataGenerator"` 를 `src/`, `tests/`에 돌려 형제 디렉토리에 대한 경로/모듈 참조가 전혀 없는지 확인한다(문서 파일 `PRD.md`/`PLAN.md`/`CLAUDE.md` 내 서술적 언급은 허용 — 코드에서의 참조만 금지).

---

## Phase 1 — 스캐폴딩 + 영속성 계층

**목표**: 프로젝트 골격과 `DataPersistence` 패턴을 이식한 영속성 계층만 먼저 완성한다. 아직 도메인 로직/콘솔 메뉴는 없다.

**참조 PoC**:
- `DataPersistence/src/datapersistence/json_repository.py` — `JsonRepository`의 시그니처(`create`/`list_all`/`find`/`update`/`delete`), `{"next_id", "records":[...]}` 스키마, 매 연산 즉시 파일 반영 방식을 그대로 참고해 **새로 작성**(import 금지, 이 파일을 열어서 인터페이스만 베낀다).
- `DataPersistence/tests/test_json_repository.py`, `test_restart_persistence.py` — 이식할 테스트 케이스 목록(자동증가 id, 순서 보존, find 성공/실패, partial update, delete, 재시작 후 유지)의 참고 템플릿.
- `ConsoleMVC/pyproject.toml`, `DataPersistence/pyproject.toml` — `pythonpath = ["src"]` 컨벤션 그대로 이식.

**산출물**:
```
SampleOrderSystem/
  requirements-dev.txt
  pyproject.toml            # pythonpath = ["src"], ConsoleMVC/DataPersistence 컨벤션 이식
  data/.gitkeep
  src/sampleordersystem/
    __init__.py
    persistence/
      __init__.py
      json_repository.py    # DataPersistence PoC 패턴 이식: 엔티티 종속 없는 dict 레코드 CRUD
  tests/
    persistence/
      test_json_repository.py
```

- `JsonRepository`는 `DataPersistence`의 인터페이스(`create`/`list_all`/`find`/`update`/`delete`, `{"next_id", "records":[...]}` 스키마, 매 연산 즉시 파일 반영)를 그대로 이식(코드 import 아님, 새로 작성).

**테스트**: `test_json_repository.py` — `DataPersistence`와 동일한 CRUD 계약 검증(자동 증가 id, 순서 보존, find 성공/실패, update partial-field, delete, 재시작 후 데이터 유지).

**완료 기준**: `pytest` 전체 통과. 아직 실행 진입점(`__main__.py`)은 없어도 됨(Phase 3에서 추가).

**추후 확장(Phase 2에서 반영)**: PRD.md가 시료 등록에 "시료 ID"를 사용자 입력 항목으로 명시하고 있어, `JsonRepository`에 `create_with_id(record, record_id) -> dict | None` 메서드가 Phase 2에서 추가되었다. 기존 `create()`(자동 증가)는 그대로 유지되며 Order 등 다른 엔티티는 계속 자동 증가 방식을 쓴다. `create_with_id`는 중복 ID를 `None`으로 거부(기존 레코드 미변경)하고, 수동 지정된 id보다 `next_id`가 낮아지지 않도록(향후 자동 증가와 충돌 없게) 갱신한다.

---

## Phase 2 — 시료 관리 (Model + Controller + View, 메뉴 1개만)

**목표**: PRD "1. 시료 관리" 기능만 콘솔에서 동작하도록 만든다. 아직 주문/생산/출고/모니터링은 없다.

**참조 PoC**:
- `ConsoleMVC/src/consolemvc/model/item.py` — `Item`/`ItemStore` 대신 `Sample`/`SampleRepository`로 이름만 바꿔 CRUD 편의 메서드 패턴(목록/검색)을 참고. 단, ID는 `ConsoleMVC`처럼 자동 부여하지 않는다 — PRD가 "시료 ID"를 등록 입력 항목으로 명시하므로 사용자가 지정한 ID를 그대로 primary key로 사용한다(아래 참고). 실제 저장은 Phase 1에서 만든 `JsonRepository` 위에 얹는다(`ConsoleMVC`의 in-memory 방식이 아니라 `DataPersistence` 방식).
- `ConsoleMVC/src/consolemvc/view/item_view.py` — `render_menu`/`render_items`류 순수 문자열 렌더링 함수 패턴을 `tables.py`/`menus.py`에 이식.
- `ConsoleMVC/src/consolemvc/controller/item_controller.py` — `input_func`/`output_func` 주입 패턴, 메뉴 라우팅 구조를 `sample_controller.py`에 이식.

**산출물** (Phase 1 위에 추가):
```
  persistence/
    json_repository.py    # create_with_id(record, record_id) -> dict | None 추가 (기존 create()는 그대로 유지)
  model/
    __init__.py
    sample.py              # Sample 엔티티 + SampleRepository(JsonRepository 기반 도메인 편의 메서드)
  view/
    __init__.py
    tables.py                # 시료 표 렌더링 (재고 포함)
    menus.py                  # 시료 관리 하위 메뉴 문자열 + 등록/검색 액션별 안내 문구(render_registration_guide/render_search_guide)
  controller/
    __init__.py
    sample_controller.py     # 시료 등록/조회/검색
  tests/
    persistence/test_json_repository.py  # create_with_id 케이스 추가
    model/test_sample_model.py
    controller/test_sample_controller.py
```

- **시료 등록**: 입력 순서는 정확히 **ID → 이름 → 평균 생산시간 → 수율**. ID는 사용자가 지정하며 실제 저장소의 primary key로 그대로 사용된다(자동 증가 아님). 이미 존재하는 ID로 등록을 시도하면 기존 레코드를 덮어쓰지 않고 오류 메시지로 거부한다. 재고 초기값은 항상 0(PRD 명시, 별도 초기 재고 입력 없음).
- **시료 검색**: 한 줄 입력을 `ID: <숫자>`(정확한 ID 조회) 또는 `이름: <검색어>`(부분 문자열, 대소문자 무시)로 파싱해 분기한다. 그 외 형식(콜론 없음, 인식 불가 라벨)은 오류 메시지를 출력하고 크래시하지 않는다.
- **안내 문구 표시 시점**: 등록/검색 입력 형식 안내 문구는 시료 관리 메뉴 화면 자체에는 표시하지 않고, 사용자가 해당 메뉴(등록/검색)를 선택한 직후 입력을 받기 직전에만 출력한다.

**테스트**: `test_json_repository.py`(확장) — `create_with_id` 성공/중복 거부(원본 미변경)/next_id 전진(역행 없음). `test_sample_model.py` — 사용자 지정 ID로 등록(재고 0으로 시작), 중복 ID 등록 시 `None` 반환. `test_sample_controller.py` — 등록 입력 순서(ID 먼저), 중복 ID 오류 메시지, 목록 조회(재고 포함), `ID:`/`이름:` 검색 두 형식과 잘못된 형식의 오류 처리, 안내 문구가 메뉴 화면 자체가 아니라 액션 선택 직후에만 출력되는지.

**완료 기준**: `pytest` 전체 통과. 이 시점에서 아직 `__main__.py`(전체 메인 메뉴)는 만들지 않아도 되지만, 원한다면 시료 관리만 단독 실행되는 임시 진입점으로 수동 확인 가능.

---

## Phase 3 — 주문 접수 + 메인 메뉴 뼈대

**목표**: PRD "2. 시료 주문 (접수)" 기능과, 전체 메뉴를 오가는 메인 메뉴 루프(요약 정보 표시 포함)를 만든다. 승인/거절/생산/출고/모니터링은 아직 없다(주문은 RESERVED 상태로만 남음).

**참조 PoC**:
- `ConsoleMVC/src/consolemvc/__main__.py` — 메인 루프가 `run_once()`를 `False` 반환까지 반복 호출하는 구조를 이식, 여기에 하위 메뉴(시료 관리/주문 등) 라우팅을 추가.
- `ConsoleMVC/src/consolemvc/controller/item_controller.py` — Order용 컨트롤러도 동일한 입력/출력 함수 주입 패턴을 따른다(테스트 시 가짜 input/output로 콘솔 없이 검증 가능하도록, Phase 2와 동일 원칙).
- `DummyDataGenerator/src/dummydatagenerator/generators.py` — (참고만, 코드 이식 아님) `status` 값 집합(`RESERVED`/`CONFIRMED`/`PRODUCING`/`RELEASED`/`REJECTED`)이 이 PoC와 동일한 문자열 그대로여야 함 — 오타/철자 불일치 없도록 대조.

**산출물**:
```
  model/
    order.py                # Order 엔티티 + OrderRepository. 상태 전이는 순수 함수/메서드로, 콘솔 I/O 없이 단위 테스트 가능하게.
  controller/
    order_controller.py      # 주문 접수만 (승인/거절은 Phase 4)
  src/sampleordersystem/__main__.py   # 메인 메뉴: 요약 정보(등록 시료 수, 전체 주문 수 - RELEASED/REJECTED 제외, 생산라인 대기) + 하위 메뉴 라우팅
  tests/
    model/test_order_transitions.py     # 이 시점에는 RESERVED 생성과 REJECTED/CONFIRMED/PRODUCING 전이 로직의 순수 함수 단위 테스트(호출은 아직 컨트롤러에 연결 안 해도 전이 규칙 자체는 여기서 검증)
    controller/test_order_controller.py  # 미등록 시료 ID로 주문 불가, 접수 직후 RESERVED
```

- 주문 접수: 시료 ID, 고객명, 주문 수량 입력 → 등록되지 않은 시료 ID면 거부 → 생성 직후 `RESERVED`.
- `order.py`에 상태 전이 규칙 전체(거절/승인 분기/생산완료/출고)를 이 Phase에서 미리 구현해도 되지만, 컨트롤러에서 실제로 호출/노출하는 것은 아직 접수뿐이다. (Phase 4/5/6에서 순서대로 노출)

**완료 기준**: `pytest` 전체 통과. `python -m sampleordersystem` 실행 시 메인 메뉴가 뜨고, 시료 등록 → 주문 접수까지 콘솔에서 1회 왕복 동작.

---

## Phase 4 — 주문 승인/거절 + 생산 큐

**목표**: PRD "3. 주문 승인/거절"과 생산 큐 계산식/FIFO 큐 자체를 구현한다(생산 큐의 자동 완료 처리는 Phase 5).

**참조 PoC**: 이 Phase의 계산식(부족분/실생산량/총생산시간)과 FIFO 큐는 PRD.md 고유 로직으로, 4개 PoC 중 직접 대응하는 패턴이 없다 — `PRD.md`의 계산식 정의(위 "생산 큐 계산식" 절)를 그대로 따르고, `DummyDataGenerator`가 생성하는 `status` 값 문자열과 반드시 동일하게 유지(대조 확인).

**산출물**:
```
  model/
    production_queue.py     # FIFO 큐 + 부족분/실생산량/총생산시간 계산 (math.ceil 사용, 반올림 방향 주의)
  controller/
    order_controller.py      # 승인/거절 로직 추가 (기존 파일 확장)
  tests/
    model/test_production_queue.py
    controller/test_order_controller.py   # 승인/거절 분기 케이스 추가
```

- 접수된 주문 목록: `RESERVED` 상태만 표시.
- 승인 시 분기: 재고 충분(재고 ≥ 수량) → 즉시 `CONFIRMED`. 재고 부족(재고 < 수량) → 생산 큐 등록 + `PRODUCING` 전환, 부족분/실생산량/총생산시간 계산해 큐 항목에 기록.
- 거절 시 즉시 `REJECTED`.

**테스트**: `test_production_queue.py` — 부족분=주문수량−재고, 실생산량=`ceil(부족분/수율)`(나누어떨어지지 않는 경우 올림 방향 확인), 총생산시간=평균생산시간×실생산량, FIFO 순서 유지. `test_order_controller.py`(확장) — 승인/거절 분기, 재고충분/부족 경계값(정확히 재고=수량인 경우 CONFIRMED로 가는지).

**완료 기준**: `pytest` 전체 통과. 콘솔에서 주문 접수 → 승인(재고 부족 시 생산 큐 등록되어 PRODUCING으로 바뀜을 확인) → 승인(재고 충분 시 즉시 CONFIRMED) → 거절 세 경로 모두 1회씩 수동 확인.

---

## Phase 5 — 생산 라인 (자동 완료 처리)

**목표**: PRD "5. 생산 라인" 기능. 생산 큐의 항목이 완료되면 자동으로 `PRODUCING` → `CONFIRMED` 전환되고 재고에 반영되는 흐름을 만든다.

**참조 PoC**:
- `DataMonitor/src/datamonitor/reader.py` — "매 조회 시 디스크에서 재로드, 캐시 없음" 원칙을 참고해, 생산 라인 현황 조회도 컨트롤러가 저장소를 매번 다시 읽어 최신 상태(다른 메뉴에서 승인한 주문이 큐에 반영됨)를 반영하도록 한다.
- `DataMonitor/src/datamonitor/view.py` — 표 렌더링(순수 함수, 레코드 간 필드 상이 시 합집합 key 처리) 패턴을 큐 대기 목록 표시에 참고.

**산출물**:
```
  controller/
    production_controller.py  # 생산 라인 현황(개수/상태), 생산 현황 표기, 대기 주문 확인(FIFO), 생산 완료 자동 처리
  tests/
    controller/test_production_controller.py
```

- 생산 완료 판정 방식은 PRD가 자유 범위로 남김(실시간 타이머가 아닌, 콘솔 세션 내 "생산 라인 메뉴 진입/새로고침 시 큐 맨 앞 항목을 완료 처리" 같은 단순 모델도 허용) — 완료 시 해당 주문 `PRODUCING` → `CONFIRMED`, 생산된 수량만큼 `stock` 증가.
- 대기 주문 확인은 큐를 FIFO 순서로 출력(주문번호, 시료, 주문량, 부족분, 실생산량 등).

**테스트**: `test_production_controller.py` — 생산 큐 표시가 FIFO 순서 유지, 생산 완료 처리 시 상태 전환 및 재고 반영이 정확한지.

**완료 기준**: `pytest` 전체 통과. 콘솔에서 PRODUCING 상태 주문이 생산 라인 메뉴를 통해 CONFIRMED로 전환되고 재고가 늘어나는 것을 1회 확인.

---

## Phase 6 — 출고 처리

**목표**: PRD "6. 출고 처리" 기능.

**참조 PoC**: `ConsoleMVC/src/consolemvc/controller/item_controller.py`의 상태 변경 흐름(선택 → 조회 → 갱신 → 저장) 구조를 참고. 별도 신규 저장소 로직은 없음(Phase 1의 `JsonRepository`/Phase 3의 `OrderRepository` 재사용).

**산출물**:
```
  controller/
    shipping_controller.py   # CONFIRMED 주문 목록 표시, 출고 실행 -> RELEASED
  tests/
    controller/test_shipping_controller.py
```

**테스트**: `test_shipping_controller.py` — CONFIRMED 주문만 출고 가능(다른 상태 주문은 출고 대상 목록에 나타나지 않음/거부됨), 출고 후 `RELEASED`.

**완료 기준**: `pytest` 전체 통과. 콘솔에서 CONFIRMED 주문 하나를 출고 처리해 RELEASED로 바뀌는 것을 확인.

---

## Phase 7 — 모니터링

**목표**: PRD "4. 모니터링" 기능. 지금까지 만든 전체 상태 전이 흐름을 관찰하는 읽기 전용 화면.

**참조 PoC**:
- `DataMonitor` 전체 PoC(`reader.py`+`view.py`+`__main__.py` 조합) — "읽기 전용, 캐시 없이 매번 재로드, 표 형태 렌더링"이라는 이 PoC의 핵심 원칙을 그대로 이식. 다만 `DataMonitor`는 범용 파일 뷰어이고 여기서는 상태별 집계(REJECTED 제외)·재고 상태 판정(여유/부족/고갈)이라는 도메인 특화 집계 로직이 추가된다는 차이가 있다.
- `DummyDataGenerator`로 생성한 더미 데이터를 이 모니터링 화면에 띄워 봤을 때도 정상 표시되는지 수동 확인(포맷 호환성 재확인 — `DummyDataGenerator/PRD.md` DoD 항목과 동일한 취지).

**산출물**:
```
  controller/
    monitoring_controller.py  # 상태별 주문 수(REJECTED 제외), 시료별 재고 현황(여유/부족/고갈)
  tests/
    controller/test_monitoring_controller.py
```

- 상태별 주문 수: `RESERVED`/`CONFIRMED`/`PRODUCING`/`RELEASED`만 집계. `REJECTED`는 반드시 제외(PRD 명시 규칙, 가장 위반하기 쉬운 부분이므로 테스트로 강제).
- 재고 상태 판정: 여유(주문 대비 충분) / 부족(주문 대비 부족) / 고갈(정확히 0) — 경계값(재고=0)이 고갈로 분류되는지 반드시 테스트.

**테스트**: `test_monitoring_controller.py` — 상태별 카운트에 REJECTED 미포함, 재고 상태 3분류 경계값(0 → 고갈).

**완료 기준**: `pytest` 전체 통과. 콘솔 모니터링 화면에서 REJECTED 주문이 카운트에서 빠져 있음을 육안으로 확인.

---

## Phase 8 — 통합 마감 (End-to-End + 영속성 재확인)

**목표**: 개별 Phase에서 이미 구현된 기능들이 전체 흐름으로 이어지는지 최종 확인하고, 문서(CLAUDE.md Status 등)를 실제 구현 상태로 동기화한다. 새 기능 추가는 없음 — 통합 검증과 마무리만.

**참조 PoC**: 없음(신규 코드 없음). 대신 "단독 실행 가능성" 절의 grep 검증(형제 PoC 디렉토리에 대한 코드 레벨 참조가 없는지)을 이 Phase에서 최종적으로 한 번 더 수행한다.

**확인 사항**:
- 메인 메뉴에서 시료 등록 → 주문 접수 → 승인(재고부족 경로로 생산큐 등록) → 생산완료(자동 전환) → 출고까지 전체 흐름이 실제 콘솔에서 1회 왕복 동작(PRD DoD).
- 모니터링 화면에서 REJECTED 제외 확인(재확인).
- 프로세스 재시작 후 데이터 유지(JSON 파일 기반) 확인 — 데이터 등록 후 종료, 새 프로세스로 재실행해 동일 데이터 조회.
- `CLAUDE.md` Status를 "Implemented"로 갱신, Commands/Architecture 섹션을 실제 구현과 일치시킴.

**완료 기준**: `pytest` 전체 통과. PRD.md의 완료 기준(Definition of Done) 전 항목 충족.

---

## 전체 완료 기준 (PRD 기준, Phase 8 종료 시점 재확인)

- `pytest` 전체 통과.
- `python -m sampleordersystem` 실행 시 메인 메뉴 → 시료 등록 → 주문 접수 → 승인(재고부족 시 생산큐 등록) → 생산완료 → 출고까지 전체 흐름이 실제 콘솔에서 1회 왕복 동작.
- 모니터링 화면에서 REJECTED 주문이 상태별 카운트에서 제외됨을 육안으로도 확인.
- 재시작 후 데이터 유지(JSON 파일 기반) 확인.
