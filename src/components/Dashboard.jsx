import React, { useState, useEffect } from "react";
import { DOMAIN_GOLDEN_SAMPLES, sanitizeAndParseInput } from "../data/samples.js";
import { evaluateCoreRules } from "../core/rules.js";
import { generateInsightWithFallback } from "../ai/reporter.js";

const DOMAIN_TABS = [
  { key: "OVERLAY", label: "① 이천 포토기술팀 (Overlay & APC)" },
  { key: "MATERIAL", label: "② 소재품질팀 (CoA & 4M 변경)" },
  { key: "MARKET", label: "③ 시장전략팀 (경쟁사 실적 & Mix)" },
  { key: "VALUE_CHAIN", label: "④ 경영전략팀 (밸류체인 & ROIC)" },
  { key: "EDUCATOR", label: "⑤ 반도체 산업교육 (커리큘럼 DAG)" },
  { key: "UNIVERSAL", label: "⑥ 🌐 범용 현업 난제 엔진 (미출제 도메인/최적화/RAG)" },
];

const PERSONA_DM_GUIDES = {
  OVERLAY: {
    botId: "photo-overlay-bot (포토기술팀)",
    dm1: "[1차 DM] Overlay M3S 스펙(2.0nm) 등호 포함(>=) 여부와, 3차 고차 왜곡(HOWA) 보정 시 전공정(Etch/Dep) 박막 스트레스 Feed-forward 항을 기본 결합할지 확인 부탁드립니다.",
    dm2: "[2차 DM] 계측 병목(TAT) 해소를 위한 최소 스마트 샘플링 비율(35%)과, 포토 Chuck 간 편차 vs 전공정 Etch 챔버 편차 원인 귀속 임계치(0.35nm / 인터록 0.65nm) 기준을 확정하고 싶습니다.",
  },
  MATERIAL: {
    botId: "material-quality-bot (소재품질팀)",
    dm1: "[1차 DM] 성적서(CoA) In-Spec 불량을 막기 위해 최소 Cpk(1.33) 외에 스펙트럼 지문 코사인 유사도(0.985)와 Baseline 평균 이동(Welch t-test p<0.01) 기준을 어떻게 설정할까요?",
    dm2: "[2차 DM] 양산 배관 체류시간 초과 또는 하위 2·3차 원료사(Sub-tier)의 PCN 미승인 4M 변경 감지 시 조건부 시생산(Pilot 15%) 없이 즉시 REJECT 및 해당 로트 홀드 조치를 내리면 될까요?",
  },
  MARKET: {
    botId: "market-strategy-bot (시장전략팀)",
    dm1: "[1차 DM] 마이크론(8월 결산 FQ)과 당사/경쟁사(12월 결산 CQ) 비교 시 Calendarization 환율 기준과, 재고자산평가손실 환입(NRV Reversal)을 제거한 Underlying OPM 산출 기준을 확인하고 싶습니다.",
    dm2: "[2차 DM] 전사 Blended ASP 상승 속 범용 단가가 하락하는 'Mix 착시'나, 어닝콜 낙관 발언(부정어 제외) 대비 재고일수(DIO)가 +7일 이상 급증할 때 WARNING/VIOLATION 경보 등급 기준을 여쭙습니다.",
  },
  VALUE_CHAIN: {
    botId: "value-chain-business-bot (경영전략팀 시장분석)",
    dm1: "[1차 DM] 전방 CSP 수요 변동 시 내부 Fab/EDS 양품 다이(KGHD) 생산량과 외부 TSMC CoWoS 패키징 할당량/베이스 다이 공급량 중 어느 쪽을 절대 출하 상한선(Ceiling)으로 적용해야 할까요?",
    dm2: "[2차 DM] HBM3E/HBM4·DDR5·eSSD CAPEX 배분 시 공정 전환 손실(Conversion Loss)과 고객사 LTA 의무 물량 하한선을 최우선 Hard Constraint로 둘지, 최소 WACC 허들 레이트(%)는 얼마인지 확인 부탁드립니다.",
  },
  EDUCATOR: {
    botId: "value-chain-educator-bot (반도체 산업교육)",
    dm1: "[1차 DM] 커리큘럼 편성 시 선수과목 순환 참조(Cycle) 발견 시 즉시 VIOLATION 차단 여부와, 가용 학습시간(max_hours) 초과 시 핵심 목표 과목(target_ids) 50% 압축 보존 기준을 여쭙습니다.",
    dm2: "[2차 DM] 교육생 오개념 방지를 위해 [1단계 직관적 비유 + 2단계 공학적 물리 한계 교정(Fact Guardrail)]과 [물리 한계 ➔ 공정 돌파 ➔ 수율 ➔ 재무 임팩트] 4단계 브릿지를 필수 출력으로 고정할까요?",
  },
  UNIVERSAL: {
    botId: "범용 현업 담당자 챗봇 (식단/통근버스/카메라/OHT/PdM/수율)",
    dm1: "[1차 DM] 예산(Budget)/정원(Capacity) 상한과 필수 과업(Mandatory) 또는 보안/개인정보 제한 구역(Forbidden)이 충돌할 때 어느 제약을 절대 기준(Hard Constraint)으로 우선 적용할까요?",
    dm2: "[2차 DM] 다기간 스케줄링(연속 동일 분류 금지), 사각지대 커버리지(Set Cover), 그리고 로컬 규정 문서 근거 조항 ID(BM25 Citation) 중 리포트 최상단에 노출할 1순위 KPI는 무엇인가요?",
  },
};

const BADGE_COLORS = {
  NORMAL: { bg: "#dcfce7", text: "#166534", border: "#22c55e", label: "🟢 NORMAL (정상 승인)" },
  WARNING: { bg: "#fef9c3", text: "#854d0e", border: "#eab308", label: "🟡 WARNING (조건부/경계 경고)" },
  VIOLATION: { bg: "#fee2e2", text: "#991b1b", border: "#ef4444", label: "🔴 VIOLATION (스펙 위반/차단)" },
};

const ARCHETYPE_MODES = [
  { key: "A", label: "📊 Type A: 지표 대시보드", desc: "실시간 KPI 카드, 웨이퍼 벡터맵, 추세 차트" },
  { key: "B", label: "⚖️ Type B: 규칙/Diff 알람", desc: "Golden Spec vs 계측치 오차, Cpk, What-If 제약" },
  { key: "C", label: "📖 Type C: 규정 근거 RAG", desc: "BM25 표준 조항 Citation, 규정 Q&A 검색" },
  { key: "D", label: "🔄 Type D: 승인 워크플로우", desc: "DRAFT➔APPROVED 상태 전이, 결재/감사 로그" },
];

export default function MainWorkspaceView({ initialArchetype = "A" }) {
  const [activeArchetype, setActiveArchetype] = useState(initialArchetype);
  const [activeDomain, setActiveDomain] = useState("OVERLAY");
  const [sampleType, setSampleType] = useState("normal");
  const [rawJsonText, setRawJsonText] = useState(() =>
    JSON.stringify(DOMAIN_GOLDEN_SAMPLES.OVERLAY.normal, null, 2)
  );
  const [simulateAiError, setSimulateAiError] = useState(false);
  const [whatIfMultiplier, setWhatIfMultiplier] = useState(1.0);
  const [exportStatusMsg, setExportStatusMsg] = useState("");
  const [pythonSolverResult, setPythonSolverResult] = useState(null);
  const [coreResult, setCoreResult] = useState(() => evaluateCoreRules(DOMAIN_GOLDEN_SAMPLES.OVERLAY.normal));
  const [aiReport, setAiReport] = useState(null);
  const [auditLogs, setAuditLogs] = useState([
    {
      timestamp: new Date().toISOString().slice(11, 19),
      actor: "SYSTEM_INIT",
      domain: "OVERLAY",
      ruleId: "OVL-RULE-PASS",
      verdict: "NORMAL",
      note: "초기 80/20 결정론 코어 및 3종 골든 샘플 로드 완료",
    },
  ]);

  const runPipeline = async (inputPayload, domainKey = activeDomain, forceErr = simulateAiError) => {
    const evaluated = evaluateCoreRules(inputPayload);
    setCoreResult(evaluated);
    const report = await generateInsightWithFallback(evaluated, {
      simulateError: forceErr,
      enableLiveBridge: true,
    });
    setAiReport(report);
  };

  useEffect(() => {
    const preset = DOMAIN_GOLDEN_SAMPLES[activeDomain]?.[sampleType] || DOMAIN_GOLDEN_SAMPLES.OVERLAY.normal;
    setRawJsonText(JSON.stringify(preset, null, 2));
    runPipeline(preset, activeDomain, simulateAiError);
  }, [activeDomain, sampleType, simulateAiError]);

  const handleWhatIfChange = (mult) => {
    setWhatIfMultiplier(mult);
    try {
      const baseObj = JSON.parse(rawJsonText);
      if (baseObj.m3s_spec_nm !== undefined) baseObj.m3s_spec_nm = Number((2.0 * mult).toFixed(2));
      if (baseObj.specs && typeof baseObj.specs === "object") {
        baseObj.min_cpk = Number((1.33 / Math.max(mult, 0.5)).toFixed(2));
        for (const k of Object.keys(baseObj.specs)) {
          const baseUsl = k.toLowerCase().includes("moisture") ? 20.0 : 5.0;
          baseObj.specs[k].USL = Number((baseUsl * mult).toFixed(2));
        }
      }
      if (baseObj.pq_mix_periods?.curr) {
        baseObj.pq_mix_periods.curr.hbm_bit_share_pct = Math.min(60, Math.max(5, Math.round(20 * mult)));
        baseObj.tsv_packaging_cap_bgb = Number((12.5 * mult).toFixed(2));
      }
      if (baseObj.total_budget !== undefined) baseObj.total_budget = Math.round(250 * mult);
      if (baseObj.tsmc_cowos_alloc_bgb !== undefined) baseObj.tsmc_cowos_alloc_bgb = Number((13.5 * mult).toFixed(2));
      if (baseObj.learner_profile?.max_hours !== undefined) baseObj.learner_profile.max_hours = Math.round(24 * mult);
      setRawJsonText(JSON.stringify(baseObj, null, 2));
      runPipeline(baseObj, activeDomain, simulateAiError);
    } catch (_) {}
  };

  const handleExportSubmissionFile = async () => {
    const domKey = coreResult?.domain || activeDomain;
    const payloadToSave = {
      exportedAt: new Date().toISOString(),
      detected_domain: domKey,
      domain: domKey,
      status: coreResult?.status,
      ruleId: coreResult?.ruleId,
      score: coreResult?.score,
      solution: pythonSolverResult || coreResult,
      coreEvaluation: coreResult,
      aiSopReport: aiReport,
      auditTrail: auditLogs,
    };
    try {
      const blob = new Blob([JSON.stringify(payloadToSave, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fde_solution_output_${(coreResult?.domain || "result").toLowerCase()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      if (typeof fetch === "function") {
        await fetch("/api/export-result", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payloadToSave),
        }).catch(() => {});
      }
      setExportStatusMsg("✅ 제출용 결과 JSON 파일(output/result.json & 브라우저 다운로드) 저장 완료!");
    } catch (e) {
      setExportStatusMsg(`⚠️ 내보내기 알림: ${e.message}`);
    }
  };

  const handleLoadWorkspaceFiles = async () => {
    try {
      const res = await fetch("/api/workspace-data");
      if (res.ok) {
        const data = await res.json();
        if (data && data.payload) {
          const detectedDom = data.detectedDomain || data.payload.domain || "UNIVERSAL";
          const targetDom = DOMAIN_GOLDEN_SAMPLES[detectedDom] ? detectedDom : "UNIVERSAL";
          setActiveDomain(targetDom);
          setRawJsonText(JSON.stringify(data.payload, null, 2));
          runPipeline(data.payload, targetDom, simulateAiError);
          if (data.pythonResult) setPythonSolverResult(data.pythonResult);
          setExportStatusMsg(`📂 실제 워크스페이스 데이터(${data.sourceFile || "통합 파이프라인"}, 도메인: ${targetDom}) 자동 로드 및 분석 완료!`);
          return;
        }
      }
      setActiveDomain("UNIVERSAL");
      setExportStatusMsg("ℹ️ 로컬 CSV/JSON 스캔 모드로 전환되었습니다 (하단 JSON 편집기에 실제 데이터를 붙여넣어 즉시 분석 가능).");
    } catch (_) {
      setActiveDomain("UNIVERSAL");
    }
  };

  const handleRunPythonCrossVerify = async () => {
    try {
      const parsed = JSON.parse(rawJsonText);
      parsed.domain = parsed.domain || activeDomain;
      const res = await fetch("/api/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      if (res.ok) {
        const pyOut = await res.json();
        setPythonSolverResult(pyOut);
        setExportStatusMsg(`🐍 Python 솔버(/api/solve) 교차 검증 완료: status=${pyOut.status || "OK"}, domain=${pyOut.domain || activeDomain}`);
      }
    } catch (e) {
      setExportStatusMsg(`⚠️ Python 솔버 브릿지 알림: ${e.message}`);
    }
  };

  const handleManualEvaluate = () => {
    runPipeline(rawJsonText, activeDomain, simulateAiError);
  };

  const handleRecordApproval = (actionLabel) => {
    const entry = {
      timestamp: new Date().toISOString().slice(11, 19),
      actor: "FIELD_ENGINEER_CONFIRM",
      domain: coreResult?.domain || activeDomain,
      ruleId: coreResult?.ruleId || "MANUAL",
      verdict: `${coreResult?.status} ➔ ${actionLabel}`,
      note: `담당자 최종 책임 승인 기록 (적용 규칙: ${coreResult?.ruleId})`,
    };
    setAuditLogs((prev) => [entry, ...prev.slice(0, 7)]);
  };

  const statusStyle = BADGE_COLORS[coreResult?.status] || BADGE_COLORS.WARNING;
  const domainMeta = DOMAIN_GOLDEN_SAMPLES[activeDomain];

  return (
    <div style={{ fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif", color: "#0f172a", maxWidth: 1360, margin: "0 auto", padding: "20px 24px" }}>
      {/* 상단 헤더 */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "2px solid #e2e8f0", paddingBottom: 14, marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#2563eb", letterSpacing: 0.6 }}>
            SEMICONDUCTOR & ENTERPRISE AI EXPERT DECISION CONSOLE (80% DETERMINISTIC CORE + 20% AI SOP ADVISOR)
          </div>
          <h1 style={{ margin: "4px 0 0 0", fontSize: 22 }}>{domainMeta?.title}</h1>
          <div style={{ fontSize: 13, color: "#475569", marginTop: 2 }}>{domainMeta?.subtitle}</div>
        </div>
        <div style={{ padding: "10px 18px", borderRadius: 10, backgroundColor: statusStyle.bg, border: `2px solid ${statusStyle.border}`, color: statusStyle.text, fontWeight: 800, fontSize: 15 }}>
          {statusStyle.label}
          <div style={{ fontSize: 11, fontWeight: 600, marginTop: 3 }}>
            적용 규칙 ID: <code>{coreResult?.ruleId}</code> | 코어 점수: {coreResult?.score ?? 0}점
          </div>
        </div>
      </header>

      {/* config.toml 4대 애플리케이션 아키타입 (Type A~D) 동적 전환 바 */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", backgroundColor: "#f8fafc", padding: "8px 12px", borderRadius: 8, border: "1px solid #e2e8f0", marginBottom: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "#475569" }}>🏛️ config.toml 아키타입 모드:</span>
        {ARCHETYPE_MODES.map((am) => {
          const isSelected = activeArchetype === am.key;
          return (
            <button
              key={am.key}
              onClick={() => setActiveArchetype(am.key)}
              title={am.desc}
              style={{
                padding: "5px 12px",
                borderRadius: 6,
                border: isSelected ? "2px solid #2563eb" : "1px solid #cbd5e1",
                backgroundColor: isSelected ? "#eff6ff" : "#ffffff",
                color: isSelected ? "#1d4ed8" : "#475569",
                fontWeight: isSelected ? 800 : 500,
                fontSize: 12,
                cursor: "pointer",
                boxShadow: isSelected ? "0 1px 3px rgba(37,99,235,0.2)" : "none",
              }}
            >
              {am.label}
            </button>
          );
        })}
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#64748b" }}>
          💡 현재 활성 모드: <b>{ARCHETYPE_MODES.find((m) => m.key === activeArchetype)?.desc}</b>
        </span>
      </div>

      {/* 5대 출제 도메인 전환 탭 */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
        {DOMAIN_TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveDomain(t.key)}
            style={{
              padding: "8px 14px",
              borderRadius: 8,
              border: activeDomain === t.key ? "2px solid #1d4ed8" : "1px solid #cbd5e1",
              backgroundColor: activeDomain === t.key ? "#eff6ff" : "#ffffff",
              color: activeDomain === t.key ? "#1e40af" : "#334155",
              fontWeight: activeDomain === t.key ? 700 : 500,
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 3종 골든 샘플 원클릭 검증 바 + AI 장애 시뮬레이션 토글 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "#f1f5f9", padding: "12px 16px", borderRadius: 10, marginBottom: 18, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "#334155" }}>⚡ 3종 골든 샘플 원클릭 검증:</span>
          <button
            onClick={() => setSampleType("normal")}
            style={{ padding: "7px 14px", borderRadius: 6, border: "1px solid #16a34a", backgroundColor: sampleType === "normal" ? "#16a34a" : "#ffffff", color: sampleType === "normal" ? "#fff" : "#166534", fontWeight: 700, cursor: "pointer" }}
          >
            [정상 샘플 입력 (NORMAL)]
          </button>
          <button
            onClick={() => setSampleType("warning")}
            style={{ padding: "7px 14px", borderRadius: 6, border: "1px solid #ca8a04", backgroundColor: sampleType === "warning" ? "#ca8a04" : "#ffffff", color: sampleType === "warning" ? "#fff" : "#854d0e", fontWeight: 700, cursor: "pointer" }}
          >
            [경고/임계치 샘플 입력 (WARNING)]
          </button>
          <button
            onClick={() => setSampleType("violation")}
            style={{ padding: "7px 14px", borderRadius: 6, border: "1px solid #dc2626", backgroundColor: sampleType === "violation" ? "#dc2626" : "#ffffff", color: sampleType === "violation" ? "#fff" : "#991b1b", fontWeight: 700, cursor: "pointer" }}
          >
            [위반/불량 샘플 입력 (VIOLATION)]
          </button>
          <button
            onClick={() => runPipeline({ value: -999, status: "INVALID" }, activeDomain, simulateAiError)}
            style={{ padding: "7px 12px", borderRadius: 6, border: "1px dashed #64748b", backgroundColor: "#fff", color: "#475569", fontSize: 12, cursor: "pointer" }}
          >
            🧪 센티널(-999/Null) 방어 테스트
          </button>
          <button
            onClick={handleLoadWorkspaceFiles}
            style={{ padding: "7px 12px", borderRadius: 6, border: "1px solid #0284c7", backgroundColor: "#e0f2fe", color: "#0369a1", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
          >
            📂 실제 과제 파일(CSV/JSON) 자동 로드
          </button>
          <button
            onClick={handleRunPythonCrossVerify}
            style={{ padding: "7px 12px", borderRadius: 6, border: "1px solid #0d9488", backgroundColor: "#ccfbf1", color: "#0f766e", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
          >
            🐍 Python 솔버 교차 검증 (/api/solve)
          </button>
          <button
            onClick={handleExportSubmissionFile}
            style={{ padding: "7px 12px", borderRadius: 6, border: "1px solid #4f46e5", backgroundColor: "#4f46e5", color: "#ffffff", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
          >
            💾 결과 JSON 파일 Export (채점/제출용)
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: "#1e40af" }}>
            🎛️ What-If 제약/임계치 배율 ({Math.round(whatIfMultiplier * 100)}%):
            <input
              type="range"
              min="0.6"
              max="1.4"
              step="0.05"
              value={whatIfMultiplier}
              onChange={(e) => handleWhatIfChange(Number(e.target.value))}
            />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: "#b91c1c", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={simulateAiError}
              onChange={(e) => setSimulateAiError(e.target.checked)}
            />
            🛡️ AI 503 장애 유발 (0.1s Fallback)
          </label>
        </div>
      </div>
      {exportStatusMsg && (
        <div style={{ marginBottom: 12, padding: "8px 14px", backgroundColor: "#ecfdf5", border: "1px solid #10b981", borderRadius: 8, fontSize: 12, fontWeight: 700, color: "#065f46" }}>
          {exportStatusMsg}
        </div>
      )}

      {/* 플랫폼 내장 페르소나 채팅봇(DM) 원클릭 질문 복사 헬퍼 */}
      <details style={{ marginBottom: 14, backgroundColor: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 10, padding: "10px 14px" }}>
        <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: 700, color: "#1e40af" }}>
          💬 플랫폼 채팅봇 ({PERSONA_DM_GUIDES[activeDomain]?.botId}) 맞춤형 DM 핵심 질의 스크립트 열기
        </summary>
        <div style={{ marginTop: 8, fontSize: 12, color: "#1e3a8a", lineHeight: 1.6 }}>
          <div>• {PERSONA_DM_GUIDES[activeDomain]?.dm1}</div>
          <div style={{ marginTop: 4 }}>• {PERSONA_DM_GUIDES[activeDomain]?.dm2}</div>
        </div>
      </details>

      {/* 메인 2-Column 그리드: 좌측 도메인별 결정론 코어(80%) 수치/SVG 시각화 + 우측 AI(20%) 리포트 및 감사 로그 */}
      <div style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: 18 }}>
        {/* 좌측: 결정론 코어(80%) 분석 결과 및 도메인 전용 시각화 */}
        <div style={{ backgroundColor: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>📐 [1차 판정 책임: 결정론 코어 80%] 수리·통계 판정 근거 및 시각화</h3>
            <span style={{ fontSize: 12, backgroundColor: "#e0f2fe", color: "#0369a1", padding: "3px 8px", borderRadius: 6, fontWeight: 700 }}>
              Pure Function (`src/core/rules.js`)
            </span>
          </div>

          {/* 도메인 1: 포토 Overlay 전용 뷰 (SVG Wafer Vector Map 포함) */}
          {coreResult?.domain === "OVERLAY" && coreResult?.metrics && (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 14 }}>
                <MetricCard title="보정 전/후 M3S (dx)" value={`${coreResult.metrics.before_m3s_dx} ➔ ${coreResult.metrics.after_m3s_dx} nm`} sub={`개선율 ${coreResult.metrics.improvement_dx_pct}%`} />
                <MetricCard title="보정 전/후 M3S (dy)" value={`${coreResult.metrics.before_m3s_dy} ➔ ${coreResult.metrics.after_m3s_dy} nm`} sub={`개선율 ${coreResult.metrics.improvement_dy_pct}%`} />
                <MetricCard title="스마트 샘플링 TAT 절감" value={`-${coreResult.smart_sampling_plan?.tat_reduction_pct}%`} sub={`${coreResult.smart_sampling_plan?.sampled_shots}/${coreResult.smart_sampling_plan?.total_shots} 샷 선별`} />
                <MetricCard title="최적 스캐너 라우팅" value={coreResult.chamber_and_scanner_matching?.optimal_scanner_routing} sub={coreResult.chamber_and_scanner_matching?.root_cause_attribution} />
              </div>

              <div style={{ display: "flex", gap: 16, alignItems: "center", backgroundColor: "#f8fafc", padding: 12, borderRadius: 10, border: "1px solid #e2e8f0" }}>
                <svg width="210" height="210" viewBox="-160 -160 320 320" style={{ backgroundColor: "#0f172a", borderRadius: "50%", flexShrink: 0 }}>
                  <circle cx="0" cy="0" r="148" fill="none" stroke="#334155" strokeWidth="2" />
                  <circle cx="0" cy="0" r="120" fill="none" stroke="#ef4444" strokeDasharray="4 4" strokeWidth="1" />
                  <line x1="-150" y1="0" x2="150" y2="0" stroke="#1e293b" />
                  <line x1="0" y1="-150" x2="0" y2="150" stroke="#1e293b" />
                  {(coreResult.wafer_vector_map || []).map((pt, i) => (
                    <g key={i}>
                      <circle cx={pt.X} cy={-pt.Y} r={pt.is_sampled ? 5 : 3} fill={pt.is_violation ? "#ef4444" : pt.is_sampled ? "#38bdf8" : "#94a3b8"} />
                      <line x1={pt.X} y1={-pt.Y} x2={pt.X + pt.raw_dx * 10} y2={-pt.Y - pt.raw_dy * 10} stroke="#f87171" strokeWidth="1.5" />
                      <line x1={pt.X} y1={-pt.Y} x2={pt.X + pt.res_dx * 10} y2={-pt.Y - pt.res_dy * 10} stroke="#4ade80" strokeWidth="2" />
                    </g>
                  ))}
                </svg>
                <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>🗺️ Wafer Overlay Vector Map (빨강: 보정 전 ➔ 초록: {coreResult.selected_order}차+FeedForward APC 보정 후)</div>
                  <div>• <b>Wafer 10-Param Correctables</b>: Tx={coreResult.physical_10param_correctables?.wafer_Tx_nm}nm, Ty={coreResult.physical_10param_correctables?.wafer_Ty_nm}nm, ScaleX={coreResult.physical_10param_correctables?.wafer_ScaleX_ppm}ppm, RotX={coreResult.physical_10param_correctables?.wafer_RotX_urad}μrad</div>
                  <div>• <b>Chuck 간 M3S 편차</b>: {coreResult.chamber_and_scanner_matching?.chuck_to_chuck_delta_nm}nm | <b>Etch 챔버 간 편차</b>: {coreResult.chamber_and_scanner_matching?.etch_chamber_delta_nm}nm</div>
                  <div>• <b>Wafer/Lot별 Rework 판정</b>: 총 {coreResult.wafer_lot_summary?.total_wafers_analyzed || 1}매 중 Rework 대상 <b>{coreResult.wafer_lot_summary?.rework_wafer_count || 0}매</b> ({(coreResult.wafer_lot_summary?.rework_lot_wafer_ids || []).join(", ") || "없음"})</div>
                  <div>• <b>격리된 센티널/결측 이상치</b>: {(coreResult.isolatedAnomalies || []).length}건 (분모에서 안전 분리 완료)</div>
                </div>
              </div>
            </div>
          )}

          {/* 도메인 2: 소재품질 전용 뷰 */}
          {coreResult?.domain === "MATERIAL" && (
            <div>
              {(coreResult.vendor_rankings || []).map((v) => (
                <div key={v.vendor_id} style={{ padding: 12, borderRadius: 8, border: "1px solid #cbd5e1", marginBottom: 10, backgroundColor: "#f8fafc" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700, marginBottom: 8 }}>
                    <span>🧪 공급사: {v.vendor_id} ({v.decision})</span>
                    <span>종합 리스크: {v.composite_risk_score}점 | 권장 배분율: {v.recommended_sourcing_share_pct}%</span>
                  </div>
                  <div style={{ fontSize: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <div>• <b>스펙트럼 지문 코사인 유사도</b>: {v.fingerprint_analysis?.cosine_similarity} (미측정 피크 편차: {v.fingerprint_analysis?.max_unmeasured_peak_deviation_pct}%)</div>
                    <div>• <b>HVM 배관 체류시간</b>: {v.hvm_scaleup_analysis?.pipe_residence_hours}h (전단응력 파티클 +{v.hvm_scaleup_analysis?.pump_shear_particle_growth_pct}%)</div>
                    <div>• <b>하위 원료사(Sub-tier) 계보</b>: {v.subtier_4m_audit?.tier2_lot_id} ➔ {v.subtier_4m_audit?.tier3_lot_id}</div>
                    <div>• <b>무단 4M 변경 적발 여부</b>: {v.subtier_4m_audit?.unapproved_4m_change_flag ? "🚨 적발 (즉시 Reject)" : "정상 승인"}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 도메인 3: 시장전략 전용 뷰 */}
          {coreResult?.domain === "MARKET" && (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 12 }}>
                <MetricCard title="Blended ASP 변동률" value={`${coreResult.pq_mix_variance_decomposition?.blended_asp_change_pct}%`} sub={`$${coreResult.pq_mix_variance_decomposition?.prev_blended_asp_usd} ➔ $${coreResult.pq_mix_variance_decomposition?.curr_blended_asp_usd}`} />
                <MetricCard title="범용(Legacy) 단가 변동률" value={`${coreResult.pq_mix_variance_decomposition?.legacy_commodity_asp_change_pct}%`} sub={coreResult.pq_mix_variance_decomposition?.mix_illusion_flag ? "🚨 Mix 착시 발생!" : "동반 상승"} />
                <MetricCard title="HBM 믹스 기여 매출액" value={`+${coreResult.pq_mix_variance_decomposition?.variance_breakdown_musd?.delta_specialty_mix_effect} M$`} sub={`총 매출변동 ${coreResult.pq_mix_variance_decomposition?.total_revenue_variance_musd} M$`} />
                <MetricCard title="최적 HBM 웨이퍼 배분율" value={`${coreResult.optimal_wafer_allocation?.hbm_wafer_share_pct ?? 30}%`} sub={`예상 영업이익 ${coreResult.optimal_wafer_allocation?.total_op_musd ?? 0} M$`} />
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ backgroundColor: "#e2e8f0", textAlign: "left" }}>
                    <th style={{ padding: 6 }}>기업 (세그먼트)</th>
                    <th style={{ padding: 6 }}>Calendar 분기</th>
                    <th style={{ padding: 6 }}>매출 (M$)</th>
                    <th style={{ padding: 6 }}>명목 OPM vs NRV제외 OPM</th>
                    <th style={{ padding: 6 }}>가이던스 괴리</th>
                  </tr>
                </thead>
                <tbody>
                  {(coreResult.calendarized_competitor_benchmarks || []).map((c, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid #e2e8f0" }}>
                      <td style={{ padding: 6, fontWeight: 700 }}>{c.company} ({c.segment})</td>
                      <td style={{ padding: 6 }}>{c.calendarized_quarter}</td>
                      <td style={{ padding: 6 }}>{c.revenue_musd}</td>
                      <td style={{ padding: 6 }}>{c.operating_margin_pct}% ➔ <b>{c.underlying_opm_pct}%</b> (환입착시 {c.nrv_distortion_pct_pt}%p)</td>
                      <td style={{ padding: 6 }}>{c.guidance_gap_pct_pt}%p</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 도메인 4: 경영전략 밸류체인 전용 뷰 */}
          {coreResult?.domain === "VALUE_CHAIN" && (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 12 }}>
                <MetricCard title="장비 발주 채찍효과 증폭" value={`+${coreResult.value_chain_and_bullwhip_analysis?.upstream_equipment_order_swing_pct}%`} sub="16개월 리드타임 누적" />
                <MetricCard title="출하 상한선 병목 노드" value={coreResult.value_chain_and_bullwhip_analysis?.binding_bottleneck_node} sub={`상한 ${coreResult.value_chain_and_bullwhip_analysis?.effective_shippable_ceiling_bgb} B_Gb`} />
                <MetricCard title="미출하 좌초 다이 재고" value={`${coreResult.value_chain_and_bullwhip_analysis?.stranded_unshipped_die_inventory_bgb} B_Gb`} sub={`손실 ${coreResult.value_chain_and_bullwhip_analysis?.stranded_holding_loss_musd} M$`} />
                <MetricCard title="포트폴리오 ROIC (vs WACC)" value={`${coreResult.capex_roic_optimization?.portfolio_weighted_roic_pct}%`} sub={`EVA +${coreResult.capex_roic_optimization?.value_created_eva_musd} M$`} />
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>📊 LTA 의무물량 & 공정 전환 손실(Conversion Loss) 반영 CAPEX ROIC 최적 포트폴리오 배분표</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginBottom: 10 }}>
                <thead>
                  <tr style={{ backgroundColor: "#e2e8f0", textAlign: "left" }}>
                    <th style={{ padding: 6 }}>제품군</th>
                    <th style={{ padding: 6 }}>Die Penalty</th>
                    <th style={{ padding: 6 }}>전환손실률</th>
                    <th style={{ padding: 6 }}>LTA 의무하한</th>
                    <th style={{ padding: 6 }}>배정 웨이퍼 (k)</th>
                    <th style={{ padding: 6 }}>배정 CAPEX (M$)</th>
                    <th style={{ padding: 6 }}>ROIC (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {(coreResult.capex_roic_optimization?.optimal_product_allocations || []).map((p, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid #e2e8f0" }}>
                      <td style={{ padding: 6, fontWeight: 700 }}>{p.product}</td>
                      <td style={{ padding: 6 }}>{p.die_penalty}x</td>
                      <td style={{ padding: 6 }}>{p.conv_loss_pct}%</td>
                      <td style={{ padding: 6 }}>{p.lta_floor_k}k</td>
                      <td style={{ padding: 6, fontWeight: 700, color: "#1d4ed8" }}>{p.allocated_wafers_k}k</td>
                      <td style={{ padding: 6 }}>{p.allocated_capex_musd} M$</td>
                      <td style={{ padding: 6, fontWeight: 700, color: "#15803d" }}>{p.roic_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ fontSize: 12, backgroundColor: "#f8fafc", padding: 8, borderRadius: 8, border: "1px solid #cbd5e1" }}>
                🔗 <b>5단계 가치사슬 채찍효과 증폭 경로</b>: {(coreResult.value_chain_and_bullwhip_analysis?.bullwhip_amplification_chain || []).map((st) => `${st.node}(+${st.shock_pct}%, ${st.lead_time_months}개월)`).join(" ➔ ")}
              </div>
            </div>
          )}

          {/* 도메인 5: 반도체 산업교육 전용 뷰 */}
          {coreResult?.domain === "EDUCATOR" && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
                📚 Kahn 위상정렬 학습 경로 ({coreResult.total_scheduled_hours}h / 예산 {coreResult.budget_max_hours}h) | DAG 무결성: {coreResult.is_valid_dag ? "✅ 정상" : `🚨 순환참조(${coreResult.cycle_detected_ids?.join(", ")})`}
              </div>
              {(coreResult.misconception_diagnostics || []).length > 0 && (
                <div style={{ padding: 10, backgroundColor: "#fef2f2", border: "1px solid #f87171", borderRadius: 8, marginBottom: 10, fontSize: 12, color: "#991b1b" }}>
                  🚨 <b>교육생 사전 질문 내 오개념 자동 교정 ({coreResult.misconception_diagnostics.length}건)</b>:
                  {coreResult.misconception_diagnostics.map((mc, idx) => (
                    <div key={idx} style={{ marginTop: 3 }}>• <b>[{mc.code}]</b> {mc.fix}</div>
                  ))}
                </div>
              )}
              {(coreResult.learning_path || []).map((m) => (
                <div key={m.id} style={{ padding: 10, border: "1px solid #cbd5e1", borderRadius: 8, marginBottom: 8, backgroundColor: "#f8fafc", fontSize: 12 }}>
                  <div style={{ fontWeight: 700, color: "#1e40af" }}>[{m.id}] {m.title} ({m.hours}h, {m.schedule_mode})</div>
                  <div style={{ marginTop: 4 }}>💡 <b>1단계 직관적 비유</b>: {m.two_layer_explanation?.layer1_analogy}</div>
                  <div style={{ marginTop: 2, color: "#991b1b" }}>🛡️ <b>2단계 공학적 팩트 가드레일</b>: {m.two_layer_explanation?.layer2_fact_guardrail}</div>
                  <div style={{ marginTop: 2, color: "#166534" }}>📈 <b>4단계 밸류체인 브릿지</b>: {m.four_step_value_chain_bridge}</div>
                </div>
              ))}
            </div>
          )}

          {/* 도메인 6: 범용 현업 난제 엔진 (UNIVERSAL) 전용 뷰 */}
          {coreResult?.domain === "UNIVERSAL" && (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 12 }}>
                <MetricCard
                  title="Root-Cause 1순위 변수"
                  value={coreResult.tabular_eda_and_root_cause?.root_cause_correlations?.[0]?.feature || "N/A"}
                  sub={`상관계수 r = ${coreResult.tabular_eda_and_root_cause?.root_cause_correlations?.[0]?.pearson_r ?? 0}`}
                />
                <MetricCard
                  title="예산 집행 최적화"
                  value={`${coreResult.constrained_optimization_plan?.utilized_budget} / ${coreResult.constrained_optimization_plan?.total_budget_limit}`}
                  sub={`선정 ${coreResult.constrained_optimization_plan?.selected_plan?.length || 0}건 / 이연 ${coreResult.constrained_optimization_plan?.deferred_items?.length || 0}건`}
                />
                <MetricCard
                  title="스펙 이탈 / 이상치 격리"
                  value={`${coreResult.tabular_eda_and_root_cause?.spec_violations?.length || 0}건 / ${(coreResult.isolatedAnomalies || []).length}건`}
                  sub="3-Sigma & USL/LSL"
                />
                <MetricCard
                  title="BM25 규정 근거 조항"
                  value={coreResult.document_citation_rag?.matched_citations?.[0]?.citation_id || "NONE"}
                  sub={`Score: ${coreResult.document_citation_rag?.matched_citations?.[0]?.bm25_score ?? 0}`}
                />
              </div>
              <div style={{ fontSize: 12, backgroundColor: "#f8fafc", padding: 10, borderRadius: 8, border: "1px solid #cbd5e1", marginBottom: 8 }}>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>📋 제약조건 기반 최적 선정 과업 (Selected Optimal Plan):</div>
                {(coreResult.constrained_optimization_plan?.selected_plan || []).map((it) => (
                  <div key={it.id}>• <b>[{it.id}] {it.name}</b> — 비용: {it.cost}, 용량: {it.capacity_req}, 가치점수: {it.value} (효율: {it.efficiency})</div>
                ))}
                {(coreResult.constrained_optimization_plan?.rejected_restricted_items || []).map((rit) => (
                  <div key={rit.id} style={{ color: "#dc2626" }}>🚫 <b>[{rit.id}] {rit.name}</b> — 사유: {rit.reason} (보안/금지 구역 원천 차단)</div>
                ))}
                {(coreResult.constrained_optimization_plan?.capacitated_fleet_dispatch_plan || []).length > 0 && (
                  <div style={{ marginTop: 6, color: "#0369a1" }}>
                    🚌 <b>통근버스/OHT 배차 최적화</b>: {coreResult.constrained_optimization_plan.capacitated_fleet_dispatch_plan.map((r) => `${r.route_id}(${r.required_buses}대, 탑승률 ${r.load_factor_pct}%)`).join(", ")}
                  </div>
                )}
                {(coreResult.constrained_optimization_plan?.spatial_set_cover_plan?.covered_zones || []).length > 0 && (
                  <div style={{ marginTop: 4, color: "#0f766e" }}>
                    📹 <b>카메라/센서 Set-Cover 커버리지</b>: 커버 구역 [{coreResult.constrained_optimization_plan.spatial_set_cover_plan.covered_zones.join(", ")}] | 미커버 사각지대: {coreResult.constrained_optimization_plan.spatial_set_cover_plan.uncovered_blind_spots?.length || 0}건
                  </div>
                )}
                {(coreResult.constrained_optimization_plan?.interval_conflict_resolution?.scheduled_non_overlapping || []).length > 0 && (
                  <div style={{ marginTop: 4, color: "#7c3aed" }}>
                    ⏱️ <b>시간창(Time-Window) 비충돌 스케줄</b>: {coreResult.constrained_optimization_plan.interval_conflict_resolution.scheduled_non_overlapping.map((s) => `${s.id}[${s.window}]`).join(", ")} (충돌 재조정 {coreResult.constrained_optimization_plan.interval_conflict_resolution.resolved_conflicts?.length || 0}건)
                  </div>
                )}
              </div>
              {(coreResult.document_citation_rag?.matched_citations || []).length > 0 && (
                <div style={{ fontSize: 12, backgroundColor: "#eff6ff", padding: 10, borderRadius: 8, border: "1px solid #bfdbfe" }}>
                  <b>📖 BM25 원문 출처(Citation) 하이라이트</b>: [{coreResult.document_citation_rag.matched_citations[0].citation_id}] {coreResult.document_citation_rag.matched_citations[0].excerpt}
                </div>
              )}
            </div>
          )}

          {pythonSolverResult && (
            <div style={{ marginTop: 12, padding: 10, backgroundColor: "#f0fdfa", border: "1px solid #5eead4", borderRadius: 8, fontSize: 12 }}>
              <div style={{ fontWeight: 700, color: "#0f766e", marginBottom: 4 }}>
                🐍 Python 결정론 솔버 교차 검증 결과 (`/api/solve` Sub-Agent Bridge)
              </div>
              <pre style={{ margin: 0, maxHeight: 140, overflowY: "auto", fontSize: 11, backgroundColor: "#ffffff", padding: 8, borderRadius: 6, border: "1px solid #ccfbf1" }}>
                {JSON.stringify(pythonSolverResult, null, 2)}
              </pre>
            </div>
          )}

          {/* 실시간 입력 JSON 편집기 */}
          <details style={{ marginTop: 14 }}>
            <summary style={{ cursor: "pointer", fontSize: 12, fontWeight: 700, color: "#475569" }}>
              🛠️ 실시간 테스트 입력 페이로드(JSON) 직접 수정 및 재검증 열기
            </summary>
            <textarea
              value={rawJsonText}
              onChange={(e) => setRawJsonText(e.target.value)}
              rows={7}
              style={{ width: "100%", marginTop: 8, fontFamily: "monospace", fontSize: 12, padding: 8, borderRadius: 6, border: "1px solid #cbd5e1" }}
            />
            <button
              onClick={handleManualEvaluate}
              style={{ marginTop: 6, padding: "6px 14px", backgroundColor: "#2563eb", color: "#fff", border: "none", borderRadius: 6, fontWeight: 700, cursor: "pointer" }}
            >
              입력 JSON으로 결정론 코어 즉시 재실행
            </button>
          </details>
        </div>

        {/* 우측: 구조화된 AI 어드바이저(20%) 리포트 및 책임/감사 로그 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ backgroundColor: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>🤖 [보조 조언: AI 어드바이저 20%] 원인 가설 및 현업 SOP</h3>
              <span style={{ fontSize: 11, backgroundColor: aiReport?.recoveredFrom ? "#fef2f2" : "#f0fdf4", color: aiReport?.recoveredFrom ? "#b91c1c" : "#15803d", padding: "3px 8px", borderRadius: 6, fontWeight: 700, border: "1px solid currentColor" }}>
                {aiReport?.source} ({aiReport?.modelUsed})
              </span>
            </div>

            <div style={{ fontSize: 13, backgroundColor: "#f8fafc", padding: 12, borderRadius: 8, borderLeft: "4px solid #2563eb", marginBottom: 12, lineHeight: 1.5 }}>
              {aiReport?.summary}
            </div>

            <div style={{ fontSize: 12, fontWeight: 700, color: "#334155", marginBottom: 6 }}>🔍 핵심 원인 귀속 가설 (Root-Cause Attribution):</div>
            <ul style={{ margin: "0 0 12px 0", paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
              {(aiReport?.rootCauseHypotheses || []).map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ul>

            <div style={{ fontSize: 12, fontWeight: 700, color: "#334155", marginBottom: 6 }}>📋 현업 권장 표준 조치(SOP) 체크리스트:</div>
            <ul style={{ margin: "0 0 12px 0", paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
              {(aiReport?.recommendedSopActions || []).map((act, i) => (
                <li key={i}>{act}</li>
              ))}
            </ul>

            <div style={{ fontSize: 11, color: "#64748b", backgroundColor: "#f1f5f9", padding: 10, borderRadius: 6 }}>
              ⚖️ <b>책임 소재(Accountability) 원칙</b>: {aiReport?.accountabilityNote}
            </div>
          </div>

          {/* 현업 담당자 최종 의사결정 승인 및 감사 로그 (Audit Trail) */}
          <div style={{ backgroundColor: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 18 }}>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>
              ✍️ [최종 의사결정 책임: 현업 담당자] 조치 확정 및 감사 로그 (Audit Trail)
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <button
                onClick={() => handleRecordApproval("SOP_ACTION_APPROVED")}
                style={{ flex: 1, padding: "8px 10px", backgroundColor: "#0f172a", color: "#fff", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: "pointer" }}
              >
                ✅ 코어 판정 승인 및 SOP 집행 기록
              </button>
              <button
                onClick={() => handleRecordApproval("CONDITIONAL_HOLD_ESCALATED")}
                style={{ flex: 1, padding: "8px 10px", backgroundColor: "#b45309", color: "#fff", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: "pointer" }}
              >
                ⚠️ 예외 보류(Hold) 및 파트장 에스컬레이션
              </button>
            </div>
            <div style={{ maxHeight: 130, overflowY: "auto", fontSize: 11, borderTop: "1px solid #e2e8f0", paddingTop: 8 }}>
              {auditLogs.map((log, i) => (
                <div key={i} style={{ marginBottom: 4, color: "#334155" }}>
                  <code>[{log.timestamp}]</code> <b>{log.domain}</b> ({log.ruleId}) — {log.verdict}: {log.note}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, sub }) {
  return (
    <div style={{ backgroundColor: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 12px" }}>
      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600 }}>{title}</div>
      <div style={{ fontSize: 15, fontWeight: 800, color: "#0f172a", marginTop: 4 }}>{value}</div>
      <div style={{ fontSize: 11, color: "#2563eb", marginTop: 2 }}>{sub}</div>
    </div>
  );
}

