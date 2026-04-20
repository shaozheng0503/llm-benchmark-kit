.PHONY: help install dev discover cases stress stress-medium stress-high authenticity summary full lint format test clean

PY ?= python3
MODELS ?= $(TARGET_MODELS)

help:
	@echo "LLM Benchmark Kit — 常用任务"
	@echo ""
	@echo "  make install         安装运行时依赖"
	@echo "  make dev             安装依赖 + dev 工具 (ruff / pytest)"
	@echo ""
	@echo "  make discover        拉取 /v1/models，落库到 data/raw/"
	@echo "  make cases           对 TARGET_MODELS 跑能力测试"
	@echo "  make stress          低档位压测"
	@echo "  make stress-medium   中档位压测"
	@echo "  make stress-high     高档位压测"
	@echo "  make authenticity    真伪鉴别"
	@echo "  make summary         合并最近一次三类结果"
	@echo "  make full            上述 discover→cases→stress→authenticity→summary 串行跑完"
	@echo ""
	@echo "  make lint            ruff 静态检查"
	@echo "  make format          ruff 自动格式化"
	@echo "  make test            pytest 运行测试"
	@echo "  make clean           清空 reports/ 与 data/raw/ 生成物"
	@echo ""
	@echo "可覆盖变量:"
	@echo "  PY=python3.12 make cases"
	@echo "  MODELS=gpt-4o-mini,claude-sonnet-4-5 make cases"

install:
	$(PY) -m pip install -r requirements.txt

dev:
	$(PY) -m pip install -e ".[dev]"

discover:
	$(PY) scripts/discover_models.py

cases:
	$(PY) scripts/run_cases.py $(if $(MODELS),--models $(MODELS),)

stress:
	$(PY) scripts/run_stress.py --tiers low $(if $(MODELS),--models $(MODELS),)

stress-medium:
	$(PY) scripts/run_stress.py --tiers medium $(if $(MODELS),--models $(MODELS),)

stress-high:
	$(PY) scripts/run_stress.py --tiers high $(if $(MODELS),--models $(MODELS),)

authenticity:
	$(PY) scripts/run_authenticity.py $(if $(MODELS),--models $(MODELS),)

summary:
	$(PY) scripts/build_summary.py

full: discover cases stress authenticity summary

lint:
	$(PY) -m ruff check .

format:
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

test:
	$(PY) -m pytest

clean:
	rm -rf reports/cases reports/stress reports/authenticity reports/summary reports/smoke
	rm -rf data/raw/*.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
