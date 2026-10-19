// Enterprise Knowledge RAG Console - Frontend Logic
// Strict corporate standards, zero emojis, real-time SSE stream processing

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const statDocs = document.getElementById("stat-docs");
  const statChunks = document.getElementById("stat-chunks");
  const statEmbed = document.getElementById("stat-embed");
  const statModel = document.getElementById("stat-model");
  const btnClearDb = document.getElementById("btn-clear-db");
  const footerMode = document.getElementById("footer-system-mode");

  // Tabs
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  // Upload Tab
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const selectedFileDisplay = document.getElementById("selected-file-display");
  const selectedFileName = document.getElementById("selected-file-name");
  const btnSubmitUpload = document.getElementById("btn-submit-upload");

  // Path Tab
  const formPathIngest = document.getElementById("form-path-ingest");
  const inputFilePath = document.getElementById("input-file-path");
  const btnSubmitPath = document.getElementById("btn-submit-path");

  // Telemetry Elements
  const telemetryStatusBadge = document.getElementById("telemetry-status-badge");
  const ingestLogConsole = document.getElementById("ingest-log-console");
  const stepParse = document.getElementById("step-parse");
  const stepChunk = document.getElementById("step-chunk");
  const stepEmbed = document.getElementById("step-embed");
  const stepIndex = document.getElementById("step-index");

  // Query Elements
  const formQuery = document.getElementById("form-query");
  const queryInput = document.getElementById("query-input");
  const btnSubmitQuery = document.getElementById("btn-submit-query");
  const queryTelemetryIndicator = document.getElementById("query-telemetry-indicator");
  const queryStatusText = document.getElementById("query-status-text");
  const qstepSearch = document.getElementById("qstep-search");
  const qstepStage1 = document.getElementById("qstep-stage1");
  const qstepSynth = document.getElementById("qstep-synth");
  const qstepStage2 = document.getElementById("qstep-stage2");

  // Privacy Audit & Telemetry Elements
  const privacyAuditCard = document.getElementById("privacy-audit-card");
  const auditStatusBadge = document.getElementById("audit-status-badge");
  const auditModeText = document.getElementById("audit-mode-text");
  const s1Status = document.getElementById("s1-status");
  const s1Category = document.getElementById("s1-category");
  const s1Rule = document.getElementById("s1-rule");
  const s2Verdict = document.getElementById("s2-verdict");
  const s2Leakage = document.getElementById("s2-leakage");
  const s2Latency = document.getElementById("s2-latency");

  // Response Elements
  const answerBox = document.getElementById("answer-box");
  const responseTimeBadge = document.getElementById("response-time-badge");
  const citationsSection = document.getElementById("citations-section");
  const citationCountBadge = document.getElementById("citation-count-badge");
  const citationsGrid = document.getElementById("citations-grid");

  // Provider Elements
  const btnProviderOpenrouter = document.getElementById("btn-provider-openrouter");
  const btnProviderGemini = document.getElementById("btn-provider-gemini");
  const btnProviderOllama = document.getElementById("btn-provider-ollama");
  const privacyPill = document.getElementById("privacy-pill");
  const statProvider = document.getElementById("stat-provider");
  const ollamaNoticeBanner = document.getElementById("ollama-notice-banner");
  const btnDismissNotice = document.getElementById("btn-dismiss-notice");

  let currentSelectedFile = null;
  let activeProvider = "gemini";
  let providersInfo = null;

  // 1. Provider & Privacy Management
  async function checkProviders() {
    try {
      const res = await fetch("/api/providers");
      if (!res.ok) return;
      providersInfo = await res.json();
      activeProvider = providersInfo.active_provider || "gemini";
      updateProviderUI(activeProvider);
    } catch (e) {
      console.warn("Failed to query providers:", e);
    }
  }

  function updateProviderUI(provider) {
    activeProvider = provider;
    [btnProviderGemini, btnProviderOllama, btnProviderOpenrouter].forEach(b => {
      if (b) b.classList.remove("active");
    });

    if (provider === "openrouter") {
      if (btnProviderOpenrouter) btnProviderOpenrouter.classList.add("active");
      if (privacyPill) {
        privacyPill.className = "privacy-pill cloud";
        privacyPill.textContent = "OpenRouter Free Online";
      }
      if (statProvider) statProvider.textContent = "OpenRouter";
      if (ollamaNoticeBanner) ollamaNoticeBanner.classList.add("hidden");
      footerMode.textContent = "Mode: Free Online Model (Meta Llama 3.3 70B via OpenRouter)";
    } else if (provider === "ollama") {
      if (btnProviderOllama) btnProviderOllama.classList.add("active");
      if (privacyPill) {
        privacyPill.className = "privacy-pill offline";
        privacyPill.textContent = "100% Offline & Private";
      }
      if (statProvider) statProvider.textContent = "Ollama";

      const ollamaData = providersInfo?.providers?.ollama;
      if (ollamaNoticeBanner) {
        if (ollamaData && !ollamaData.available) {
          ollamaNoticeBanner.classList.remove("hidden");
        } else {
          ollamaNoticeBanner.classList.add("hidden");
        }
      }
      footerMode.textContent = "Mode: 100% Air-Gapped Local Offline (Zero Cloud Egress via Ollama)";
    } else {
      if (btnProviderGemini) btnProviderGemini.classList.add("active");
      if (privacyPill) {
        privacyPill.className = "privacy-pill cloud";
        privacyPill.textContent = "Cloud Processing";
      }
      if (statProvider) statProvider.textContent = "Gemini";
      if (ollamaNoticeBanner) ollamaNoticeBanner.classList.add("hidden");
      footerMode.textContent = "Mode: Cloud Production (Google Gemini API)";
    }
  }

  async function setProvider(provider) {
    try {
      const res = await fetch("/api/provider/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: provider })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to switch provider");
      }
      const data = await res.json();
      appendLog(getCurTime(), "SYSTEM", `Switched provider to ${provider.toUpperCase()} (${data.chat_model} / ${data.embed_model})`);
      await checkProviders();
      await refreshStats();
    } catch (e) {
      appendLog(getCurTime(), "ERROR", `Failed to switch provider: ${e.message}`);
    }
  }

  if (btnProviderOpenrouter) {
    btnProviderOpenrouter.addEventListener("click", () => setProvider("openrouter"));
  }
  if (btnProviderGemini) {
    btnProviderGemini.addEventListener("click", () => setProvider("gemini"));
  }
  if (btnProviderOllama) {
    btnProviderOllama.addEventListener("click", () => setProvider("ollama"));
  }
  if (btnDismissNotice && ollamaNoticeBanner) {
    btnDismissNotice.addEventListener("click", () => {
      ollamaNoticeBanner.classList.add("hidden");
    });
  }

  // 2. Initialize Stats
  async function refreshStats() {
    try {
      const res = await fetch("/api/stats");
      if (!res.ok) return;
      const data = await res.json();
      if (statProvider) {
        statProvider.textContent = data.active_provider === "ollama" ? "Ollama" : (data.active_provider === "openrouter" ? "OpenRouter" : "Gemini");
      }
      statDocs.textContent = data.total_documents || 0;
      statChunks.textContent = data.total_chunks || 0;
      statEmbed.textContent = data.embed_model || "gemini-embedding-001";
      statModel.textContent = data.chat_model || "meta-llama/llama-3.3-70b-instruct:free";

      if (data.active_provider === "ollama") {
        footerMode.textContent = "Mode: 100% Air-Gapped Local Offline (Zero Cloud Egress via Ollama)";
      } else if (data.active_provider === "openrouter") {
        footerMode.textContent = "Mode: Free Online Models (OpenRouter - Meta Llama 3.3 70B)";
      } else if (data.mock_mode) {
        footerMode.textContent = "Mode: Offline / Test Mode (Set GEMINI_API_KEY in .env for live Gemini)";
      } else {
        footerMode.textContent = "Mode: Live Production (Google Gemini API Connected)";
      }
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  }

  checkProviders();
  refreshStats();

  // 2. Tab Switching
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetTab = document.getElementById(btn.dataset.tab);
      if (targetTab) targetTab.classList.add("active");
    });
  });

  // 3. File Selection & Drag-and-Drop
  ["dragenter", "dragover"].forEach(event => {
    dropZone.addEventListener(event, (e) => {
      e.preventDefault();
      dropZone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach(event => {
    dropZone.addEventListener(event, (e) => {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  });

  function handleSelectedFile(file) {
    currentSelectedFile = file;
    selectedFileName.textContent = file.name;
    selectedFileDisplay.classList.remove("hidden");
  }

  // 4. Ingestion Telemetry Helpers
  function resetTelemetry() {
    [stepParse, stepChunk, stepEmbed, stepIndex].forEach(s => {
      s.className = "step-item";
    });
    telemetryStatusBadge.className = "telemetry-status active";
    telemetryStatusBadge.textContent = "PROCESSING";
    ingestLogConsole.innerHTML = "";
  }

  function appendLog(time, stage, msg) {
    const line = document.createElement("div");
    line.className = "log-line";
    line.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-stage">[${stage}]</span> <span class="log-msg">${escapeHtml(msg)}</span>`;
    ingestLogConsole.appendChild(line);
    ingestLogConsole.scrollTop = ingestLogConsole.scrollHeight;
  }

  function updateStepper(stage) {
    if (stage === "PARSE" || stage === "INGEST") {
      stepParse.className = "step-item running";
    } else if (stage === "CHUNK") {
      stepParse.className = "step-item done";
      stepChunk.className = "step-item running";
    } else if (stage === "EMBED") {
      stepParse.className = "step-item done";
      stepChunk.className = "step-item done";
      stepEmbed.className = "step-item running";
    } else if (stage === "INDEX") {
      stepParse.className = "step-item done";
      stepChunk.className = "step-item done";
      stepEmbed.className = "step-item done";
      stepIndex.className = "step-item running";
    } else if (stage === "COMPLETE") {
      stepParse.className = "step-item done";
      stepChunk.className = "step-item done";
      stepEmbed.className = "step-item done";
      stepIndex.className = "step-item done";
    }
  }

  // 5. Ingestion via Upload File (SSE Stream)
  btnSubmitUpload.addEventListener("click", async () => {
    if (!currentSelectedFile) return;

    btnSubmitUpload.disabled = true;
    resetTelemetry();

    const formData = new FormData();
    formData.append("file", currentSelectedFile);

    try {
      const response = await fetch("/api/ingest/upload", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        throw new Error(`Upload failed with status: ${response.status}`);
      }

      await readSSEStream(response);
    } catch (err) {
      appendLog(getCurTime(), "ERROR", err.message);
      telemetryStatusBadge.className = "telemetry-status error";
      telemetryStatusBadge.textContent = "FAILED";
    } finally {
      btnSubmitUpload.disabled = false;
      refreshStats();
    }
  });

  // 6. Ingestion via Local Path (SSE Stream)
  formPathIngest.addEventListener("submit", async (e) => {
    e.preventDefault();
    const filePath = inputFilePath.value.trim();
    if (!filePath) return;

    btnSubmitPath.disabled = true;
    resetTelemetry();

    try {
      const response = await fetch("/api/ingest/path", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: filePath })
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Path ingestion failed with status: ${response.status}`);
      }

      await readSSEStream(response);
    } catch (err) {
      appendLog(getCurTime(), "ERROR", err.message);
      telemetryStatusBadge.className = "telemetry-status error";
      telemetryStatusBadge.textContent = "FAILED";
    } finally {
      btnSubmitPath.disabled = false;
      refreshStats();
    }
  });

  // SSE Stream Consumer
  async function readSSEStream(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // Keep partial line

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const jsonStr = line.replace("data: ", "").trim();
          if (!jsonStr) continue;

          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "progress") {
              appendLog(event.timestamp, event.stage, event.message);
              updateStepper(event.stage);
            } else if (event.type === "result") {
              updateStepper("COMPLETE");
              telemetryStatusBadge.className = "telemetry-status success";
              telemetryStatusBadge.textContent = "COMPLETED";
              appendLog(
                event.timestamp,
                "COMPLETE",
                `Indexed ${event.result.filename} (${event.result.chunks_indexed} chunks, ${event.result.elapsed_seconds}s)`
              );
            } else if (event.type === "error") {
              appendLog(event.timestamp, "ERROR", event.error);
              telemetryStatusBadge.className = "telemetry-status error";
              telemetryStatusBadge.textContent = "ERROR";
            }
          } catch (e) {
            console.error("Failed to parse SSE line:", line, e);
          }
        }
      }
    }
  }

  // 7. Grounded Query Execution with Automatic Dual-Stage Privacy Enforcement
  formQuery.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    btnSubmitQuery.disabled = true;
    queryTelemetryIndicator.classList.remove("hidden");
    if (privacyAuditCard) privacyAuditCard.classList.add("hidden");
    citationsSection.classList.add("hidden");
    citationsGrid.innerHTML = "";
    answerBox.innerHTML = '<span class="placeholder-text">Executing Dual-Stage Privacy Enforced Query...</span>';

    // Step 1: Retrieve
    if (qstepSearch) qstepSearch.className = "q-step active";
    if (qstepStage1) qstepStage1.className = "q-step";
    if (qstepSynth) qstepSynth.className = "q-step";
    if (qstepStage2) qstepStage2.className = "q-step";
    queryStatusText.textContent = "Step 1: Retrieving candidates from vector store...";

    try {
      // Step 2: Stage 1 Filter
      setTimeout(() => {
        if (qstepStage1) qstepStage1.className = "q-step active";
        queryStatusText.textContent = "Step 2: Stage 1 Query-Adaptive Privacy & Secret Shield check...";
      }, 250);

      // Step 3: Synthesis
      setTimeout(() => {
        if (qstepSynth) qstepSynth.className = "q-step active";
        queryStatusText.textContent = `Step 3: Synthesizing response via ${activeProvider === "ollama" ? "local Ollama" : "Gemini"}...`;
      }, 500);

      // Step 4: Stage 2 Leakage Guard
      setTimeout(() => {
        if (qstepStage2) qstepStage2.className = "q-step active";
        queryStatusText.textContent = "Step 4: Stage 2 Output Leakage Prevention scan...";
      }, 750);

      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          top_k: 4,
          enforce_privacy: true
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Query failed with status ${res.status}`);
      }

      const data = await res.json();

      // Render Privacy Audit Card
      if (data.privacy_audit && privacyAuditCard) {
        const audit = data.privacy_audit;
        privacyAuditCard.classList.remove("hidden");

        if (auditStatusBadge) {
          const statusText = audit.overall_status.replace(/_/g, " ");
          auditStatusBadge.textContent = statusText;
          if (audit.overall_status === "RESTRICTED") {
            auditStatusBadge.style.backgroundColor = "#DC2626";
          } else {
            auditStatusBadge.style.backgroundColor = "#059669";
          }
        }
        if (auditModeText) {
          auditModeText.textContent = audit.offline_guarantee || (activeProvider === "ollama" ? "100% Air-Gapped Offline" : "Cloud Hybrid Mode");
        }

        const s1 = audit.stage_1_query_adaptive_filter || {};
        if (s1Status) {
          s1Status.textContent = s1.status || "PASSED";
          s1Status.style.color = (s1.status === "RESTRICTED") ? "#F87171" : "#38BDF8";
        }
        if (s1Category) {
          s1Category.textContent = s1.category ? s1.category.replace(/_/g, " ") : "NONE";
        }
        if (s1Rule) {
          s1Rule.textContent = s1.rule_matched || "PASSED";
        }

        const s2 = audit.stage_2_output_leakage_prevention || {};
        if (s2Verdict) {
          s2Verdict.textContent = s2.verdict ? s2.verdict.replace(/_/g, " ") : "PASS";
          s2Verdict.style.color = (s2.verdict === "LEAKAGE_SUPPRESSED") ? "#F87171" : "#34D399";
        }
        if (s2Leakage) {
          s2Leakage.textContent = s2.leakage_detected ? "DETECTED" : "NONE";
        }
        if (s2Latency) {
          s2Latency.textContent = `${audit.privacy_latency_ms || 0}ms`;
        }
      }

      responseTimeBadge.textContent = `${data.processing_time_ms} ms`;

      // Check for Restricted Privacy Violation
      if (data.is_restricted) {
        citationsSection.classList.add("hidden");
        citationsGrid.innerHTML = "";

        answerBox.innerHTML = `
          <div class="restriction-alert-box">
            <div class="restriction-alert-header">
              <span class="restriction-badge">[ACCESS RESTRICTED: PRIVACY VIOLATION PREVENTED]</span>
              <span class="restriction-category-pill">${escapeHtml(data.restriction_category || "CREDENTIALS_AND_AUTH")}</span>
            </div>
            <div class="restriction-alert-body">
              <p>${escapeHtml(data.answer)}</p>
            </div>
            <div class="restriction-alert-footer">
              <span>Zero-Contamination Guarantee: Prompt injection was blocked at Stage 1. No confidential context or citations were exposed.</span>
            </div>
          </div>
        `;
        queryStatusText.textContent = `Halted in ${data.processing_time_ms} ms [Restricted Access Blocked by Policy]`;
      } else {
        // Legitimate query - Display Answer with Styled Citation Tags
        let formattedAnswer = escapeHtml(data.answer);

        // Highlight privacy redaction tokens with security pills if any
        formattedAnswer = formattedAnswer.replace(/\[(REDACTED|PROTECTED)_[A-Z_]+\]/g, (match) => {
          return `<span class="privacy-redacted-badge">${match}</span>`;
        });

        // Replace bracketed citations like [Source 1] with styled pills
        formattedAnswer = formattedAnswer.replace(/\[Source\s*(\d+)\]/gi, (match, p1) => {
          return `<span class="brand-badge" style="cursor:pointer;" onclick="highlightCitation(${p1})">${match}</span>`;
        });

        // Preserve newlines
        answerBox.innerHTML = formattedAnswer.replace(/\n\n/g, "<br><br>").replace(/\n/g, "<br>");

        // Display Citations & Evidence
        if (data.citations && data.citations.length > 0) {
          citationCountBadge.textContent = `${data.citations.length} Source${data.citations.length !== 1 ? "s" : ""}`;
          citationsGrid.innerHTML = "";

          data.citations.forEach(c => {
            const card = document.createElement("div");
            card.className = "citation-card";
            card.id = `citation-card-${c.citation_id}`;
            card.innerHTML = `
              <div class="citation-card-header">
                <span class="citation-source">[Source ${c.citation_id}] ${escapeHtml(c.source_filename)}</span>
                <span class="citation-page">Page ${c.page_number}</span>
                <span class="citation-score">Relevance: ${c.relevance_percent}%</span>
              </div>
              <div class="citation-excerpt">${escapeHtml(c.excerpt)}</div>
            `;
            citationsGrid.appendChild(card);
          });

          citationsSection.classList.remove("hidden");
        } else {
          citationsSection.classList.add("hidden");
        }

        queryStatusText.textContent = `Completed in ${data.processing_time_ms} ms [Privacy Audit Verified]`;
      }
    } catch (err) {
      answerBox.innerHTML = `<span style="color: #FFFFFF; background: #141414; border: 1px solid #404040; padding: 4px 8px; border-radius: 3px;">[ERROR] ${escapeHtml(err.message)}</span>`;
      queryStatusText.textContent = "Query failed";
    } finally {
      btnSubmitQuery.disabled = false;
      if (qstepSearch) qstepSearch.className = "q-step";
      if (qstepStage1) qstepStage1.className = "q-step";
      if (qstepSynth) qstepSynth.className = "q-step";
      if (qstepStage2) qstepStage2.className = "q-step";
    }
  });

  // Citation highlighting helper
  window.highlightCitation = function(citationId) {
    const card = document.getElementById(`citation-card-${citationId}`);
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "center" });
      card.style.borderColor = "#2563EB";
      card.style.borderLeftColor = "#2563EB";
      card.style.backgroundColor = "#F1F5F9";
      setTimeout(() => {
        card.style.borderColor = "";
        card.style.borderLeftColor = "";
        card.style.backgroundColor = "";
      }, 1500);
    }
  };



  // 8. Clear Index Action
  btnClearDb.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to clear all indexed vectors from the knowledge base?")) {
      return;
    }

    try {
      const res = await fetch("/api/clear", { method: "POST" });
      if (res.ok) {
        appendLog(getCurTime(), "INDEX", "Knowledge base successfully cleared.");
        answerBox.innerHTML = '<p class="placeholder-text">Knowledge base cleared. Ingest a document to begin.</p>';
        citationsSection.classList.add("hidden");
        refreshStats();
      }
    } catch (err) {
      alert("Failed to clear database: " + err.message);
    }
  });

  // Utilities
  function getCurTime() {
    const now = new Date();
    return now.toTimeString().split(" ")[0];
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
