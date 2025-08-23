// File: static/js/app.js

const socket = io();
let charts = {};
let testingActive = false;
let testResults = [];
let currentRunId = null;

document.addEventListener("DOMContentLoaded", function () {
    initializeCharts();
    setupEventListeners();
    setupSocketListeners();
});

function initializeCharts() {
    charts.pdr = initChart("pdrChart", "line", "rgba(54, 162, 235, 1)", "PDR (%)");
    charts.delay = initChart("delayChart", "line", "rgba(255, 99, 132, 1)", "Delay (ms)");
    charts.throughput = initChart("throughputChart", "line", "rgba(75, 192, 192, 1)", "Throughput (kbps)");
    charts.energy = initChart("energyChart", "line", "rgba(153, 102, 255, 1)", "Energy (J)");
}

function initChart(canvasId, type, bgColor, yLabel) {
    const ctx = document.getElementById(canvasId).getContext("2d");
    return new Chart(ctx, {
        type: type,
        data: {
            labels: [],
            datasets: [{
                label: yLabel,
                data: [],
                backgroundColor: bgColor,
                borderColor: bgColor,
                borderWidth: 2,
                fill: false,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 200 },
            scales: {
                x: {
                    type: "linear",
                    position: "bottom",
                    title: { display: true, text: "Time (s)" },
                    min: 0,
                    grid: { color: 'rgba(0,0,0,0.1)' }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: yLabel },
                    grid: { color: 'rgba(0,0,0,0.1)' }
                }
            },
            plugins: {
                legend: { 
                    display: true,
                    labels: { usePointStyle: true }
                },
                tooltip: { 
                    mode: "index", 
                    intersect: false,
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    borderColor: bgColor,
                    borderWidth: 1
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

function setupEventListeners() {
    // Auto-testing buttons
    document.getElementById("btnStartAutoTest").addEventListener("click", startAutoTesting);
    document.getElementById("btnStopAutoTest").addEventListener("click", stopAutoTesting);
    
    // Manual mode toggle
    document.getElementById("manualMode").addEventListener("change", function() {
        const manualControls = document.getElementById("manualControls");
        manualControls.style.display = this.checked ? "block" : "none";
    });
    
    // Manual simulation button
    document.getElementById("btnStartManual").addEventListener("click", startManualSimulation);
}

function setupSocketListeners() {
    socket.on("testing_started", handleTestingStarted);
    socket.on("current_test", handleCurrentTest);
    socket.on("protocol_test_update", handleProtocolTestUpdate);
    socket.on("test_completed", handleTestCompleted);
    socket.on("testing_complete", handleTestingComplete);
    socket.on("testing_stopped", handleTestingStopped);
    socket.on("testing_error", handleTestingError);
    
    // Manual simulation listeners
    socket.on("sim_update", handleSimulationUpdate);
    socket.on("sim_complete", handleSimulationComplete);
    socket.on("sim_stopped", handleSimulationStopped);
    socket.on("sim_error", handleSimulationError);
}

function startAutoTesting() {
    if (testingActive) return;
    
    const numScenarios = parseInt(document.getElementById("numScenarios").value);
    
    testingActive = true;
    testResults = [];
    
    // Update UI
    document.getElementById("btnStartAutoTest").disabled = true;
    document.getElementById("btnStopAutoTest").disabled = false;
    updateStatus("Starting intelligent protocol testing...", "running");
    
    // Hide previous results
    hideResults();
    
    // Clear charts
    clearAllCharts();
    
    fetch("/start_auto_testing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ num_scenarios: numScenarios })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "started") {
            console.log("Auto-testing started successfully");
        } else {
            throw new Error(data.error || "Failed to start testing");
        }
    })
    .catch(err => {
        console.error("Error starting auto-testing:", err);
        alert("Error starting testing: " + err.message);
        resetTestingUI();
    });
}

function stopAutoTesting() {
    fetch("/stop_auto_testing", {
        method: "POST",
        headers: { "Content-Type": "application/json" }
    })
    .then(res => res.json())
    .then(data => {
        console.log("Stopping auto-testing...");
        updateStatus("Stopped", "running");
    });
}

function startManualSimulation() {
    const config = {
        protocol: document.getElementById("protocol").value,
        numNodes: parseInt(document.getElementById("numNodes").value),
        simTime: 45,
        areaSize: 1000,
        nodeSpeed: parseInt(document.getElementById("nodeSpeed").value),
        txRange: parseInt(document.getElementById("txRange").value),
        pauseTime: 2,
        trafficLoad: 15
    };
    
    clearAllCharts();
    hideResults();
    
    fetch("/start_simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config)
    })
    .then(res => res.json())
    .then(data => {
        currentRunId = data.run_id;
        updateStatus(`Running manual test with ${config.protocol}...`, "running");
    })
    .catch(err => {
        console.error("Error starting manual simulation:", err);
        alert("Error: " + err.message);
    });
}

function handleTestingStarted(data) {
    console.log("Testing started:", data);
    
    // Show scenarios info
    const scenariosDiv = document.getElementById("scenariosInfo");
    const scenariosList = document.getElementById("scenariosList");
    
    let scenariosHtml = "";
    data.scenarios.forEach((scenario, index) => {
        scenariosHtml += `
            <div class="scenario-badge">
                ${scenario.id}: ${scenario.nodes} nodes, ${scenario.area}, ${scenario.speed}
            </div>
        `;
    });
    
    scenariosList.innerHTML = scenariosHtml;
    scenariosDiv.style.display = "block";
    
    // Show progress container
    document.getElementById("progressContainer").style.display = "block";
    updateProgress(0, `Testing ${data.protocols.length} protocols across ${data.scenarios.length} scenarios...`);
}

function handleCurrentTest(data) {
    console.log("Current test:", data);
    
    // Update current test badge
    const currentTestBadge = document.getElementById("currentTest");
    currentTestBadge.textContent = `${data.protocol} - ${data.scenario}`;
    currentTestBadge.style.display = "inline";
    
    // Update progress
    updateProgress(data.progress, `Testing ${data.protocol} on ${data.scenario}...`);
    updateStatus(`Testing ${data.protocol} on ${data.scenario}...`, "running");
}

function handleProtocolTestUpdate(data) {
    if (data.type === "metrics") {
        // Update charts with current test data
        updateChart(charts.pdr, data.time, data.pdr);
        updateChart(charts.delay, data.time, data.delay);
        updateChart(charts.throughput, data.time, data.throughput);
        updateChart(charts.energy, data.time, data.energy);
        
        // Update network visualization
        updateNetworkVisualization(data);
    }
}

function handleTestCompleted(data) {
    console.log("Test completed:", data);
    testResults.push(data.result);
    
    // Add to results table
    addResultToTable(data.result);
    
    // Show results table if first result
    if (testResults.length === 1) {
        document.getElementById("resultsTable").style.display = "block";
    }
}

function handleTestingComplete(data) {
    console.log("Testing complete:", data);
    testingActive = false;
    
    // Update UI
    resetTestingUI();
    updateStatus("Testing completed! Analysis ready.", "complete");
    
    // Hide progress and current test
    document.getElementById("progressContainer").style.display = "none";
    document.getElementById("currentTest").style.display = "none";
    
    // Show winner banner
    showWinnerBanner(data);
    
    // Show protocol rankings
    showProtocolRankings(data);
    
    // Clear charts for final display
    clearAllCharts();
}

function handleTestingStopped(data) {
    console.log("Testing stopped:", data);
    testingActive = false;
    resetTestingUI();
    updateStatus("Testing was stopped by user.", "ready");
    document.getElementById("progressContainer").style.display = "none";
}

function handleTestingError(data) {
    console.error("Testing error:", data);
    testingActive = false;
    resetTestingUI();
    updateStatus("Error occurred during testing.", "error");
    alert("Testing error: " + data.error);
}

function handleSimulationUpdate(data) {
    if (data.run_id && currentRunId && data.run_id !== currentRunId) {
        return; // Ignore outdated updates
    }
    
    if (data.type === "metrics") {
        updateChart(charts.pdr, data.time, data.pdr);
        updateChart(charts.delay, data.time, data.delay);
        updateChart(charts.throughput, data.time, data.throughput);
        updateChart(charts.energy, data.time, data.energy);
        updateNetworkVisualization(data);
    }
}

function handleSimulationComplete(data) {
    updateStatus("Manual simulation completed.", "complete");
}

function handleSimulationStopped(data) {
    updateStatus("Manual simulation stopped.", "ready");
}

function handleSimulationError(data) {
    updateStatus("Manual simulation error.", "error");
    alert("Simulation error: " + data.error);
}

function showWinnerBanner(analysis) {
    const banner = document.getElementById("winnerBanner");
    const details = document.getElementById("winnerDetails");
    
    const confidence = (analysis.recommendation_confidence * 100).toFixed(1);
    const score = analysis.best_score.toFixed(1);
    
    details.innerHTML = `
        <h3>${analysis.best_protocol}</h3>
        <p class="mb-2">Overall Score: <strong>${score}/100</strong></p>
        <p class="mb-2">Confidence Level: <strong>${confidence}%</strong></p>
        <div class="confidence-bar">
            <div class="confidence-fill" style="width: ${confidence}%"></div>
        </div>
        <p class="small">
            Based on ${analysis.total_tests} tests across ${analysis.scenarios_tested} different network scenarios
        </p>
    `;
    
    banner.style.display = "block";
    banner.classList.add("fade-in");
}

function showProtocolRankings(analysis) {
    const rankingsDiv = document.getElementById("protocolRankings");
    const cardsContainer = document.getElementById("rankingCards");
    
    let cardsHtml = "";
    
    analysis.protocol_rankings.forEach(([protocol, score], index) => {
        const details = analysis.detailed_results[protocol];
        const rankClass = `rank-${index + 1}`;
        const rankIcon = index === 0 ? "fas fa-trophy" : 
                        index === 1 ? "fas fa-medal" : 
                        index === 2 ? "fas fa-award" : "fas fa-certificate";
        
        cardsHtml += `
            <div class="col-md-6 col-lg-3">
                <div class="card protocol-card ${rankClass}">
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-2">
                            <i class="${rankIcon} me-2"></i>
                            <h5 class="mb-0">${protocol}</h5>
                            <span class="badge bg-secondary ms-auto">#${index + 1}</span>
                        </div>
                        <div class="protocol-score">Score: ${score.toFixed(1)}/100</div>
                        <div class="small text-muted">
                            <div>PDR: ${(details.avg_pdr * 100).toFixed(1)}%</div>
                            <div>Delay: ${details.avg_delay.toFixed(1)}ms</div>
                            <div>Throughput: ${details.avg_throughput.toFixed(1)} kbps</div>
                            <div>Consistency: ${details.consistency.toFixed(1)}%</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    cardsContainer.innerHTML = cardsHtml;
    rankingsDiv.style.display = "block";
    rankingsDiv.classList.add("fade-in");
}

function addResultToTable(result) {
    const tbody = document.getElementById("testResultsBody");
    const row = tbody.insertRow();
    
    row.innerHTML = `
        <td><strong>${result.protocol}</strong></td>
        <td>${result.scenario}</td>
        <td>${(result.pdr * 100).toFixed(1)}%</td>
        <td>${result.delay.toFixed(1)}</td>
        <td>${result.throughput.toFixed(1)}</td>
        <td>${result.energy.toFixed(0)}</td>
        <td><span class="badge bg-primary">${result.score.toFixed(1)}</span></td>
    `;
    
    row.classList.add("fade-in");
}

function updateChart(chart, time, value) {
    const t = typeof time === "number" ? time : parseFloat(time) || 0;
    
    if (chart.data.labels.length >= 100) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }
    
    chart.data.labels.push(parseFloat(t.toFixed(1)));
    chart.data.datasets[0].data.push(value === undefined ? null : value);
    
    if (chart.options.scales?.x && t > (chart.options.scales.x.suggestedMax || 0)) {
        chart.options.scales.x.suggestedMax = Math.ceil(t / 10) * 10;
    }
    
    chart.update('none');
}

function updateNetworkVisualization(data) {
    const container = document.getElementById("network-canvas");
    const width = container.clientWidth;
    const height = container.clientHeight;
    
    const svg = d3.select("#network-canvas")
        .selectAll("svg")
        .data([null])
        .join("svg")
        .attr("width", width)
        .attr("height", height);
    
    const xScale = d3.scaleLinear()
        .domain([0, data.areaSize[0]])
        .range([50, width - 50]);
    
    const yScale = d3.scaleLinear()
        .domain([0, data.areaSize[1]])
        .range([50, height - 50]);
    
    // Draw links
    svg.selectAll(".link")
        .data(data.links)
        .join("line")
        .attr("class", "link link-line")
        .attr("x1", d => xScale(data.nodes.find(n => n.id === d.source).x))
        .attr("y1", d => yScale(data.nodes.find(n => n.id === d.source).y))
        .attr("x2", d => xScale(data.nodes.find(n => n.id === d.target).x))
        .attr("y2", d => yScale(data.nodes.find(n => n.id === d.target).y));
    
    // Draw nodes
    const node = svg.selectAll(".node")
        .data(data.nodes, d => d.id)
        .join("g")
        .attr("class", "node")
        .attr("transform", d => `translate(${xScale(d.x)},${yScale(d.y)})`);
    
    node.selectAll("circle")
        .data(d => [d])
        .join("circle")
        .attr("class", "node-circle")
        .attr("r", 8)
        .attr("fill", d => d.energy > 70 ? "#4CAF50" : 
                         d.energy > 30 ? "#FFC107" : "#F44336")
        .attr("stroke", "#333")
        .attr("stroke-width", 2);
    
    node.selectAll("text")
        .data(d => [d])
        .join("text")
        .attr("class", "node-text")
        .attr("dy", 3)
        .text(d => d.id);
}

function updateStatus(message, type = "ready") {
    const statusText = document.getElementById("statusText");
    const statusDiv = document.getElementById("currentStatus").querySelector(".test-status");
    
    statusText.textContent = message;
    
    // Remove existing status classes
    statusDiv.classList.remove("testing-active", "testing-complete");
    
    // Add appropriate class
    if (type === "running") {
        statusDiv.classList.add("testing-active");
    } else if (type === "complete") {
        statusDiv.classList.add("testing-complete");
    }
}

function updateProgress(percentage, text) {
    const progressBar = document.getElementById("progressBar");
    const progressText = document.getElementById("progressText");
    
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = text;
}

function clearAllCharts() {
    Object.values(charts).forEach(chart => {
        chart.data.labels = [];
        chart.data.datasets[0].data = [];
        chart.update('none');
    });
}

function hideResults() {
    document.getElementById("winnerBanner").style.display = "none";
    document.getElementById("protocolRankings").style.display = "none";
    document.getElementById("resultsTable").style.display = "none";
    document.getElementById("scenariosInfo").style.display = "none";
    
    // Clear table
    document.getElementById("testResultsBody").innerHTML = "";
}

function resetTestingUI() {
    document.getElementById("btnStartAutoTest").disabled = false;
    document.getElementById("btnStopAutoTest").disabled = true;
}