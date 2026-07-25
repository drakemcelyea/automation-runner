let currentAccent = "primary";
let runsChart = null;
let pendingPlaybook = null;
let pendingTarget = "all";
let pendingExtraVars = "";

function showView(view) {
    document.querySelectorAll(".view").forEach(e => e.classList.add("d-none"));
    document.getElementById("view-" + view).classList.remove("d-none");

    const sidebar = document.getElementById("sidebar");
    const main = document.getElementById("main-content");
    const logoutBtn = document.getElementById("logout-btn");

    if (view === "app") {
        sidebar.classList.remove("d-none");
        main.className = "col-md-10 p-4";
        logoutBtn.classList.remove("d-none");
    } else {
        sidebar.classList.add("d-none");
        main.className = "col-md-12 p-4";
        logoutBtn.classList.add("d-none");
    }
}

function showTab(tab, btn) {
    document.querySelectorAll(".tab-section").forEach(t => t.classList.add("d-none"));
    document.getElementById("tab-" + tab).classList.remove("d-none");

    document.querySelectorAll(".list-group-item").forEach(b => b.classList.remove("active"));
    if (btn) btn.classList.add("active");

    if (tab === "dashboard") {
        loadStats();
        loadPlaybooks();
        loadTargetGroups();
    }
    if (tab === "inventory") loadInventory();
    if (tab === "playbooks") loadPlaybooks();
    if (tab === "runs") loadRuns();
    if (tab === "settings") {
        loadSettings();
        loadVaultStatus();
    }
}

function login() {
    document.getElementById("login-error").innerText = "";

    fetch("/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            username: document.getElementById("login-user").value,
            password: document.getElementById("login-pass").value
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "ok") {
            document.getElementById("user-label").innerText = "Signed in as " + data.user;
            showView("app");
            init();
        } else {
            document.getElementById("login-error").innerText = data.message || "Invalid login";
        }
    })
    .catch(err => {
        document.getElementById("login-error").innerText = err;
    });
}

function logout() {
    fetch("/logout")
        .then(() => {
            document.getElementById("user-label").innerText = "";
            showView("login");
        });
}

function init() {
    loadSettings();
    checkHealth();
    loadStats();
    loadPlaybooks();
    loadTargetGroups();
    loadRuns();
    loadInventory();
}

function checkHealth() {
    fetch("/health")
        .then(() => {
            document.getElementById("health").className = "badge text-bg-success";
            document.getElementById("health").innerText = "Healthy";
        })
        .catch(() => {
            document.getElementById("health").className = "badge text-bg-danger";
            document.getElementById("health").innerText = "Down";
        });
}

function statusBadge(status) {
    if (status === "successful") return "badge text-bg-success";
    if (status === "failed") return "badge text-bg-danger";
    if (status === "error") return "badge text-bg-warning";
    return "badge text-bg-secondary";
}

function loadStats() {
    fetch("/stats")
        .then(r => r.json())
        .then(d => {
            document.getElementById("stat-total").innerText = d.total;
            document.getElementById("stat-successful").innerText = d.successful;
            document.getElementById("stat-failed").innerText = d.failed;
            document.getElementById("stat-errors").innerText = d.errors;
            renderRunsChart(d);
        });
}

function clearOutput() {
    document.getElementById("output").innerText = "Waiting...";
}

function loadTargetGroups() {
    fetch("/inventory/groups")
        .then(r => r.json())
        .then(d => {
            const select = document.getElementById("run-target");
            if (!select) return;

            select.innerHTML = d.groups.map(group => `
                <option value="${group}">${group}</option>
            `).join("");
        });
}

function runPlaybook(playbookOverride = null, targetOverride = null, extraVarsOverride = null) {
    const btn = document.getElementById("run-btn");
    const playbook = playbookOverride || document.getElementById("run-playbook").value;
    const target = targetOverride || document.getElementById("run-target").value;
    const extraVars = extraVarsOverride !== null ? extraVarsOverride : document.getElementById("extra-vars").value;

    btn.disabled = true;
    btn.innerText = "Running...";
    document.getElementById("output").innerText = "Starting playbook...";

    fetch("/run-demo", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            playbook: playbook,
            target: target,
            extra_vars: extraVars
        })
    })
    .then(r => r.json())
    .then(d => {
        document.getElementById("output").innerText = JSON.stringify(d, null, 2);
        if (d.run_id) loadLogs(d.run_id);
        updateLastRunBanner(d);
        loadStats();
        loadRuns();
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerText = "Run";
    });
}

function loadLogs(runId) {
    fetch(`/run-demo/${runId}/logs`)
        .then(r => r.json())
        .then(d => {
            document.getElementById("output").innerText = d.logs || "No logs.";
        });
}

function loadInventory() {
    fetch("/inventory")
        .then(r => r.json())
        .then(d => {
            const container = document.getElementById("inventory-table");

            if (!d.hosts || d.hosts.length === 0) {
                container.innerHTML = `<div class="alert alert-secondary mb-0">No hosts yet. Add one from the Inventory tab.</div>`;
                return;
            }

            container.innerHTML = `
                <table class="table table-sm align-middle">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>IP</th>
                            <th>Type</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${d.hosts.map(h => `
                            <tr>
                                <td>${h.name || ""}</td>
                                <td><code>${h.ip || ""}</code></td>
                                <td>${h.type || ""}</td>
                                <td>
                                    <span class="badge ${h.enabled ? "text-bg-success" : "text-bg-secondary"}">
                                        ${h.enabled ? "Enabled" : "Disabled"}
                                    </span>
                                </td>
                                <td>${h.created_at || ""}</td>
                                <td class="text-end">
                                    <button class="btn btn-sm btn-outline-secondary" onclick="toggleHost('${h.id}')">Toggle</button>
                                    <button class="btn btn-sm btn-outline-danger" onclick="deleteHost('${h.id}')">Delete</button>
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        });
}

function addHost() {
    const name = document.getElementById("host-name").value.trim();
    const ip = document.getElementById("host-ip").value.trim();
    const type = document.getElementById("host-type").value;

    if (!name || !ip) {
        showToast("Name and IP required");
        return;
    }

    fetch("/inventory/add", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name, ip, type})
    })
    .then(() => {
        document.getElementById("host-name").value = "";
        document.getElementById("host-ip").value = "";
        loadInventory();
        loadTargetGroups();
    });
}

function deleteHost(id) {
    if (!confirm("Delete this host?")) return;
    fetch(`/inventory/${id}`, {method: "DELETE"})
        .then(() => {
            loadInventory();
            loadTargetGroups();
        });
}

function toggleHost(id) {
    fetch(`/inventory/${id}/toggle`, {method: "POST"})
        .then(() => {
            loadInventory();
            loadTargetGroups();
        });
}

function loadRuns() {
    fetch("/runs")
        .then(r => r.json())
        .then(d => {
            const container = document.getElementById("run-history");

            if (!d.runs || d.runs.length === 0) {
                container.innerHTML = `<div class="alert alert-secondary mb-0">No runs yet. Run a playbook from the Dashboard.</div>`;
                return;
            }

            container.innerHTML = `
                <table class="table table-sm align-middle">
                    <thead>
                        <tr>
                            <th>Run ID</th>
                            <th>Playbook</th>
                            <th>Target</th>
                            <th>Status</th>
                            <th>RC</th>
                            <th>Duration</th>
                            <th>Started</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${d.runs.map(run => `
                            <tr>
                                <td><code>${run.run_id}</code></td>
                                <td>${run.playbook || ""}</td>
                                <td><code>${run.target || "all"}</code></td>
                                <td><span class="${statusBadge(run.status)}">${run.status}</span></td>
                                <td>${run.rc}</td>
                                <td>${run.duration ?? ""}s</td>
                                <td>${run.started_at || ""}</td>
                                <td>
                                    <button class="btn btn-sm btn-outline-primary" onclick="openRunDetails('${run.run_id}')">
                                        View Logs
                                    </button>
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        });
}

function clearRuns() {
    if (!confirm("Clear run history?")) return;
    fetch("/runs", {method: "DELETE"})
        .then(() => {
            loadRuns();
            loadStats();
        });
}

function loadPlaybooks() {
    fetch("/playbooks")
        .then(r => r.json())
        .then(d => {
            const select = document.getElementById("run-playbook");
            const list = document.getElementById("playbook-list");

            if (!d.playbooks || d.playbooks.length === 0) {
                select.innerHTML = "";
                list.innerHTML = `<p class="text-muted mb-0">No playbooks found.</p>`;
                return;
            }

            select.innerHTML = d.playbooks.map(p => `<option value="${p.name}">${p.name}</option>`).join("");

            list.innerHTML = d.playbooks.map(p => `
                <button class="list-group-item list-group-item-action" onclick="openPlaybook('${p.name}')">
                    ${p.name}
                </button>
            `).join("");
        });
}

function openPlaybook(name) {
    fetch(`/playbooks/${name}`)
        .then(r => r.json())
        .then(d => {
            document.getElementById("playbook-name").value = d.name || name;
            document.getElementById("editor-title").innerText = d.name || name;
            document.getElementById("playbook-editor").value = d.content || "";
            document.getElementById("syntax-output").innerText = "No output.";
            document.getElementById("syntax-status").className = "badge text-bg-secondary";
            document.getElementById("syntax-status").innerText = "No check";
        });
}

function savePlaybook() {
    const name = document.getElementById("playbook-name").value.trim();
    const content = document.getElementById("playbook-editor").value;

    if (!name) {
        showToast("Playbook name required");
        return;
    }

    fetch("/playbooks/save", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name, content})
    })
    .then(r => r.json())
    .then(d => {
        document.getElementById("editor-title").innerText = d.name || name;
        loadPlaybooks();
    });
}

function syntaxCheck() {
    const name = document.getElementById("playbook-name").value.trim();

    if (!name) {
        showToast("Select or save a playbook first");
        return;
    }

    document.getElementById("syntax-status").className = "badge text-bg-secondary";
    document.getElementById("syntax-status").innerText = "Checking...";
    document.getElementById("syntax-output").innerText = "Checking syntax...";

    fetch(`/playbooks/${name}/syntax-check`, {method: "POST"})
        .then(r => r.json())
        .then(d => {
            document.getElementById("syntax-output").innerText = d.output || "No output.";
            document.getElementById("syntax-status").className =
                d.status === "successful" ? "badge text-bg-success" : "badge text-bg-danger";
            document.getElementById("syntax-status").innerText = d.status;
        });
}

function deletePlaybook() {
    const name = document.getElementById("playbook-name").value.trim();

    if (!name || !confirm("Delete " + name + "?")) return;

    fetch(`/playbooks/${name}`, {method: "DELETE"})
        .then(() => {
            document.getElementById("playbook-name").value = "";
            document.getElementById("playbook-editor").value = "";
            document.getElementById("editor-title").innerText = "Editor";
            loadPlaybooks();
        });
}

function loadSettings() {
    fetch("/settings")
        .then(r => r.json())
        .then(d => {
            document.getElementById("theme").value = d.theme || "light";
            document.getElementById("accent").value = d.accent || "primary";
            document.getElementById("logging-enabled").checked = d.logging_enabled !== false;
            applySettings(d);
        });
}

function saveSettings() {
    const settings = {
        theme: document.getElementById("theme").value,
        accent: document.getElementById("accent").value,
        logging_enabled: document.getElementById("logging-enabled").checked
    };

    fetch("/settings", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(settings)
    })
    .then(r => r.json())
    .then(applySettings);
}

function applySettings(settings) {
    const theme = settings.theme || "light";
    const accent = settings.accent || "primary";

    document.documentElement.setAttribute("data-bs-theme", theme);

    const navbar = document.getElementById("top-navbar");
    const userLabel = document.getElementById("user-label");
    const logoutBtn = document.getElementById("logout-btn");

    if (theme === "dark") {
        document.body.classList.add("grafana");
        navbar.className = "navbar navbar-dark px-4";
        userLabel.className = "text-light small";
        logoutBtn.className = "btn btn-sm btn-outline-light";
    } else {
        document.body.classList.remove("grafana");
        navbar.className = "navbar navbar-light bg-white border-bottom px-4";
        userLabel.className = "text-dark small";
        logoutBtn.className = "btn btn-sm btn-outline-dark";
    }

    currentAccent = accent;

    document.querySelectorAll(".accent-btn").forEach(btn => {
        btn.className = btn.className.replace(/btn-(primary|success|danger|warning|info)/g, `btn-${accent}`);
    });
}

function loadVaultStatus() {
    fetch("/vault/status")
        .then(r => r.json())
        .then(d => {
            const status = document.getElementById("vault-status");

            if (!status) return;

            const ok = d.vault_file_exists && d.vault_password_file_exists && d.vault_encrypted;

            status.className = ok
                ? "alert alert-success mt-3 mb-0"
                : "alert alert-warning mt-3 mb-0";

            status.innerHTML = `
                <div><strong>Vault file:</strong> ${d.vault_file_exists ? "Exists" : "Missing"}</div>
                <div><strong>Password file:</strong> ${d.vault_password_file_exists ? "Exists" : "Missing"}</div>
                <div><strong>Encrypted:</strong> ${d.vault_encrypted ? "Yes" : "No"}</div>
                <div class="small text-muted mt-2">${d.vault_file}</div>
            `;
        });
}

function saveVault() {
    const payload = {
        vault_password: document.getElementById("vault-password").value,
        vault_linux_password: document.getElementById("vault-linux-password").value,
        vault_linux_become_password: document.getElementById("vault-linux-become-password").value,
        vault_windows_password: document.getElementById("vault-windows-password").value
    };

    if (!payload.vault_password) {
        showToast("Vault password is required");
        return;
    }

    fetch("/vault/save", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(d => {
        showToast(d.message || d.status || "Vault updated");

        document.getElementById("vault-linux-password").value = "";
        document.getElementById("vault-linux-become-password").value = "";
        document.getElementById("vault-windows-password").value = "";

        loadVaultStatus();
    });
}

function testVault() {
    fetch("/vault/test", {method: "POST"})
        .then(r => r.json())
        .then(d => {
            showToast(d.output || d.status);

            const status = document.getElementById("vault-status");
            if (!status) return;

            status.className = d.status === "successful"
                ? "alert alert-success mt-3 mb-0"
                : "alert alert-danger mt-3 mb-0";

            status.innerText = d.output || d.status;
        });
}

function checkSession() {
    fetch("/me")
        .then(r => r.json())
        .then(d => {
            if (d.authenticated) {
                document.getElementById("user-label").innerText = "Signed in as " + d.user;
                showView("app");
                init();
            } else {
                showView("login");
                checkHealth();
            }
        })
        .catch(() => {
            showView("login");
            checkHealth();
        });
}

function showToast(message) {
    document.getElementById("toast-message").innerText = message;
    const toast = new bootstrap.Toast(document.getElementById("app-toast"));
    toast.show();
}

function renderRunsChart(stats) {
    const ctx = document.getElementById("runs-chart");

    if (!ctx) return;

    if (runsChart) {
        runsChart.destroy();
    }

    runsChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["Successful", "Failed", "Errors"],
            datasets: [{
                data: [stats.successful, stats.failed, stats.errors]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: "bottom"
                }
            }
        }
    });
}

function openRunDetails(runId) {
    document.getElementById("run-details-output").innerText = "Loading logs...";

    fetch(`/run-demo/${runId}/logs`)
        .then(r => r.json())
        .then(d => {
            document.getElementById("run-details-output").innerText = d.logs || "No logs.";
            const modal = new bootstrap.Modal(document.getElementById("runDetailsModal"));
            modal.show();
        });
}

function openRunConfirm() {
    pendingPlaybook = document.getElementById("run-playbook").value;
    pendingTarget = document.getElementById("run-target").value;
    pendingExtraVars = document.getElementById("extra-vars").value.trim();

    document.getElementById("confirm-playbook-name").innerText = pendingPlaybook;
    document.getElementById("confirm-target-name").innerText = pendingTarget;
    document.getElementById("confirm-extra-vars").innerText = pendingExtraVars || "None";

    const modal = new bootstrap.Modal(document.getElementById("confirmRunModal"));
    modal.show();
}

function confirmRunPlaybook() {
    const modalEl = document.getElementById("confirmRunModal");
    const modal = bootstrap.Modal.getInstance(modalEl);
    modal.hide();

    runPlaybook(pendingPlaybook, pendingTarget, pendingExtraVars);
}

function updateLastRunBanner(run) {
    const banner = document.getElementById("last-run-banner");

    if (!run) {
        banner.classList.add("d-none");
        return;
    }

    banner.className = run.status === "successful"
        ? "alert alert-success"
        : "alert alert-danger";

    banner.innerHTML = `
        Last run: <strong>${run.playbook}</strong> —
        target <strong>${run.target || "all"}</strong> —
        ${run.status} —
        rc ${run.rc} —
        ${run.duration}s
    `;
}

setInterval(() => {
    const runsTabVisible = !document.getElementById("tab-runs").classList.contains("d-none");
    const dashboardVisible = !document.getElementById("tab-dashboard").classList.contains("d-none");

    if (runsTabVisible || dashboardVisible) {
        loadStats();
        loadRuns();
    }
}, 10000);

checkSession();