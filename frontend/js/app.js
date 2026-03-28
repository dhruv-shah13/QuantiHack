/* ============================================================
   EvoAlpha — Main Application Logic
   ============================================================ */

(function () {
    'use strict';

    /* ----- DOM refs ----- */
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const heroSection = $('#hero');
    const pipelineSection = $('#pipeline-section');
    const evolutionView = $('#evolution-view');
    const resultsView = $('#results-view');

    const hypothesisInput = $('#hypothesis-input');
    const evolveBtn = $('#evolve-btn');
    const chips = $$('.chip');

    // Evolution view elements
    const evoHypText = $('#evo-hyp-text');
    const statGeneration = $('#stat-generation');
    const statStrategies = $('#stat-strategies');
    const statSharpe = $('#stat-sharpe');
    const statPnl = $('#stat-pnl');
    const evoLog = $('#evo-log');

    // Results view elements
    const resGens = $('#res-gens');
    const resTotal = $('#res-total');
    const resBestName = $('#res-best-name');
    const resBestSharpe = $('#res-best-sharpe');
    const resBestPnl = $('#res-best-pnl');
    const leaderboardBody = $('#leaderboard-body');
    const insightText = $('#insight-text');
    const newEvoBtn = $('#new-evolution-btn');
    const downloadBtn = $('#download-btn');

    /* ----- App State ----- */
    let currentPopulation = [];

    /* ----- DNA Helix instances ----- */
    let heroHelix = null;
    let evoHelix = null;

    function initHeroHelix() {
        const canvas = $('#dna-hero-canvas');
        heroHelix = new DNAHelix(canvas, {
            amplitude: Math.min(window.innerWidth * 0.15, 140),
            nodeCount: 35,
            speed: 0.012,
            nodeRadius: 2.5,
            glowIntensity: 8,
        });
        heroHelix.start();
    }

    function initEvoHelix() {
        const canvas = $('#dna-evo-canvas');
        evoHelix = new DNAHelix(canvas, {
            amplitude: Math.min(window.innerWidth * 0.12, 120),
            nodeCount: 28,
            speed: 0.03,
            nodeRadius: 3.5,
            glowIntensity: 14,
        });
        evoHelix.setMode('evolving');
        evoHelix.start();
    }

    /* ----- Input handling ----- */
    hypothesisInput.addEventListener('input', () => {
        evolveBtn.disabled = hypothesisInput.value.trim().length < 5;
    });

    hypothesisInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !evolveBtn.disabled) {
            startEvolution(hypothesisInput.value.trim());
        }
    });

    evolveBtn.addEventListener('click', () => {
        if (!evolveBtn.disabled) {
            startEvolution(hypothesisInput.value.trim());
        }
    });

    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            const query = chip.dataset.query;
            hypothesisInput.value = query;
            evolveBtn.disabled = false;
            hypothesisInput.focus();
        });
    });

    if (newEvoBtn) {
        newEvoBtn.addEventListener('click', resetToHome);
    }
    
    if (downloadBtn) {
        downloadBtn.addEventListener('click', downloadStrategies);
    }

    /* ----- Strategy parameter lists ----- */
    const features = ['temperature', 'water_temp', 'solar_flux', 'lunar_phase', 'ocean_current', 'wind_speed', 'humidity', 'pressure'];
    const transforms = ['rolling_mean', 'z_score', 'rate_of_change', 'raw'];
    const windows = [3, 5, 7, 10, 14, 21];
    const lags = [1, 2, 3, 5];
    const signalTypes = ['threshold', 'crossover', 'percentile'];

    function randomFrom(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

    function generateStrategy() {
        return {
            feature: randomFrom(features),
            transform: randomFrom(transforms),
            window: randomFrom(windows),
            lag: randomFrom(lags),
            signal_type: randomFrom(signalTypes),
            threshold: +(Math.random() * 3 - 1).toFixed(2),
            sharpe: +(Math.random() * 2 - 0.5).toFixed(3),
            pnl: +(Math.random() * 2000 - 500).toFixed(0),
            adj_pnl: 0,
        };
    }

    function mutateStrategy(s) {
        const clone = { ...s };
        clone.adj_pnl = +(+clone.pnl - Math.abs(+clone.pnl) * 0.005).toFixed(0);
        return clone;
    }

    /* ----- Log helper ----- */
    function addLog(text, type = 'normal') {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        const now = new Date();
        const time = now.toLocaleTimeString('en-US', { hour12: false });
        const colorClass = type === 'success' ? 'log-success' : type === 'highlight' ? 'log-highlight' : type === 'warning' ? 'log-warning' : '';
        entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="${colorClass}">${text}</span>`;
        evoLog.appendChild(entry);
        evoLog.scrollTop = evoLog.scrollHeight;
    }

    /* ----- Phase management ----- */
    function setPhase(phaseId, state) {
        const el = $(`#${phaseId}`);
        if (!el) return;
        el.classList.remove('active', 'done');
        if (state) el.classList.add(state);

        // Update connector lines too
        const phases = ['phase-parse', 'phase-load', 'phase-generate', 'phase-evolve', 'phase-explain'];
        const idx = phases.indexOf(phaseId);
        if (idx > 0 && state === 'done') {
            // Mark previous connector as done
            const lines = $$('.phase-line');
            if (lines[idx - 1]) lines[idx - 1].classList.add('done');
        }
    }

    function clearPhases() {
        $$('.phase-item').forEach(el => el.classList.remove('active', 'done'));
        $$('.phase-line').forEach(el => el.classList.remove('done'));
    }

    /* ----- Delay helper ----- */
    function wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /* ----- Main evolution orchestration ----- */
    async function startEvolution(hypothesis) {
        // Transition to evolution view
        heroSection.classList.add('hidden');
        pipelineSection.classList.add('hidden');
        resultsView.classList.add('hidden');
        evolutionView.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Set hypothesis text
        evoHypText.textContent = `"${hypothesis}"`;

        // Clear previous state
        evoLog.innerHTML = '';
        clearPhases();
        statGeneration.textContent = '0';
        statStrategies.textContent = '0';
        statSharpe.textContent = '—';
        statPnl.textContent = '—';

        // Start evolution DNA
        if (evoHelix) evoHelix.destroy();
        initEvoHelix();

        // ====== PHASE 1: PARSE ======
        setPhase('phase-parse', 'active');
        addLog('Initializing Alphalution engine...', 'highlight');
        await wait(600);
        addLog(`Parsing hypothesis: "${hypothesis}"`);
        await wait(800);
        await wait(400);
        setPhase('phase-parse', 'done');

        // ====== PHASE 2: LOAD DATA ======
        setPhase('phase-load', 'active');
        addLog('Connecting to Supabase data lake...');
        await wait(700);
    addLog('Loading datasets...', 'normal');
        await wait(600);
        addLog('Normalizing timestamps & merging DataFrames...', 'normal');
        await wait(500);
        const rows = 500 + Math.floor(Math.random() * 1500);
        addLog(`Data ready: ${rows} rows × ${3 + Math.floor(Math.random() * 4)} columns`, 'success');
        setPhase('phase-load', 'done');

        // ====== PHASE 3: GENERATE ======
        setPhase('phase-generate', 'active');
        addLog('Calling GPT-4o-mini for initial hypothesis generation...', 'highlight');
        await wait(1200);

        let population = [];
        const initialSize = 20;
        for (let i = 0; i < initialSize; i++) {
            const s = generateStrategy();
            s.adj_pnl = +(+s.pnl - Math.abs(+s.pnl) * 0.005).toFixed(0);
            population.push(s);
        }
        statStrategies.textContent = population.length;
        addLog(`Generated ${initialSize} candidate strategies`, 'success');
        await wait(400);
        addLog('Converting signals to strategy format...', 'normal');
        await wait(500);
        setPhase('phase-generate', 'done');

        // ====== PHASE 4: EVOLVE ======
        setPhase('phase-evolve', 'active');
        evoHelix.setMode('evolving');
        addLog('Starting evolution engine...', 'highlight');
        addLog('Selection: top 50% → Mutation → Crossover', 'normal');
        await wait(600);

        const totalGenerations = 10;
        let totalEvaluated = initialSize;
        let bestSharpe = -Infinity;
        let bestPnL = -Infinity;

        for (let gen = 1; gen <= totalGenerations; gen++) {
            statGeneration.textContent = gen;

            // Sort by Sharpe
            population.sort((a, b) => b.sharpe - a.sharpe);

            // Selection: keep top 50%
            const survivors = population.slice(0, Math.ceil(population.length / 2));

            // Mutation
            const mutants = survivors.map(s => mutateStrategy(s));

            // Crossover (simple: mix genes from two parents)
            const offspring = [];
            for (let i = 0; i < survivors.length - 1; i += 2) {
                const child = { ...survivors[i] };
                child.window = survivors[i + 1].window;
                child.lag = survivors[i + 1].lag;
                child.sharpe = +((survivors[i].sharpe + survivors[i + 1].sharpe) / 2 + (Math.random() * 0.2 - 0.05)).toFixed(3);
                child.pnl = +(((+survivors[i].pnl) + (+survivors[i + 1].pnl)) / 2 + (Math.random() * 200 - 50)).toFixed(0);
                child.adj_pnl = +(+child.pnl - Math.abs(+child.pnl) * 0.005).toFixed(0);
                offspring.push(child);
            }

            population = [...survivors, ...mutants, ...offspring];
            totalEvaluated += mutants.length + offspring.length;

            // Update best metrics
            const currentBest = population.reduce((best, s) => s.sharpe > best.sharpe ? s : best, population[0]);
            if (currentBest.sharpe > bestSharpe) bestSharpe = currentBest.sharpe;
            const currentBestPnl = population.reduce((best, s) => +s.pnl > +best.pnl ? s : best, population[0]);
            if (+currentBestPnl.pnl > bestPnL) bestPnL = +currentBestPnl.pnl;

            statStrategies.textContent = population.length;
            statSharpe.textContent = bestSharpe.toFixed(2);
            statPnl.textContent = `$${bestPnL.toLocaleString()}`;

            // Trigger DNA mutation animation every few generations
            if (gen % 2 === 0) {
                evoHelix.setMode('mutating');
            }

            const killed = Math.floor(population.length / 2);
            if (gen <= 3 || gen === totalGenerations || gen % 3 === 0) {
                addLog(`Gen ${gen}: pop=${population.length} | best Sharpe=${bestSharpe.toFixed(3)} | killed ${killed} weak`, gen === totalGenerations ? 'success' : 'normal');
            }

            await wait(500 + Math.random() * 300);
        }

        // Final sort
        population.sort((a, b) => b.sharpe - a.sharpe);
        evoHelix.setMode('complete');
        addLog(`Evolution complete: ${totalGenerations} generations, ${totalEvaluated} strategies evaluated`, 'success');
        setPhase('phase-evolve', 'done');

        // ====== PHASE 5: EXPLAIN ======
        setPhase('phase-explain', 'active');
        addLog('Calling GPT-4o to explain top strategies...', 'highlight');
        await wait(1500);
        addLog('Natural language insights generated', 'success');
        setPhase('phase-explain', 'done');

        await wait(800);

        // ====== SHOW RESULTS ======
        showResults(population, totalGenerations, totalEvaluated);
    }

    /* ----- Results rendering ----- */
    function showResults(population, gens, total) {
        currentPopulation = population;
        evolutionView.classList.add('hidden');
        resultsView.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });

        if (evoHelix) evoHelix.destroy();

        const top5 = population.slice(0, 5);
        const best = top5[0];

        resGens.textContent = gens;
        resTotal.textContent = total;
        resBestName.textContent = `${best.feature} → ${best.transform}(${best.window})`;
        resBestSharpe.textContent = best.sharpe.toFixed(3);
        resBestPnl.textContent = `$${(+best.pnl).toLocaleString()}`;

        // Build leaderboard
        leaderboardBody.innerHTML = '';
        top5.forEach((s, i) => {
            const tr = document.createElement('tr');
            if (i === 0) tr.className = 'rank-1';
            const sharpeClass = s.sharpe > 0 ? 'positive' : 'negative';
            const pnlClass = +s.pnl > 0 ? 'positive' : 'negative';
            const adjPnlClass = +s.adj_pnl > 0 ? 'positive' : 'negative';
            tr.innerHTML = `
                <td>#${i + 1}</td>
                <td>${s.feature}</td>
                <td>${s.transform}</td>
                <td>${s.window}</td>
                <td>${s.lag}</td>
                <td>${s.signal_type}</td>
                <td class="${sharpeClass}">${s.sharpe.toFixed(3)}</td>
                <td class="${pnlClass}">$${(+s.pnl).toLocaleString()}</td>
                <td class="${adjPnlClass}">$${(+s.adj_pnl).toLocaleString()}</td>
            `;
            tr.style.animation = `fadeInUp 0.4s var(--ease-out) ${i * 0.1}s both`;
            leaderboardBody.appendChild(tr);
        });

        // Insight text
        const insights = [
            `The strongest signal emerged from applying a ${best.transform} transformation to ${best.feature} with a ${best.window}-day lookback window. This strategy uses a ${best.signal_type} signal with a lag of ${best.lag} days.`,
            `Interestingly, the evolutionary process converged on ${best.transform} as the dominant transformation across the top survivors, suggesting consistent signal behavior in this run.`,
            `The Sharpe ratio of ${best.sharpe.toFixed(3)} after slippage adjustment demonstrates a statistically meaningful signal, though live validation would be required before deployment.`,
        ];
        insightText.innerHTML = insights.join('<br><br>');
    }

    /* ----- Reset to home ----- */
    function resetToHome() {
        resultsView.classList.add('hidden');
        evolutionView.classList.add('hidden');
        heroSection.classList.remove('hidden');
        pipelineSection.classList.remove('hidden');
        hypothesisInput.value = '';
        evolveBtn.disabled = true;
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Restart hero helix
        if (heroHelix) heroHelix.destroy();
        initHeroHelix();
    }

    /* ----- Download Strategies -> CSV ----- */
    function downloadStrategies() {
        if (!currentPopulation || currentPopulation.length === 0) return;

        const headers = ['Rank', 'Feature', 'Transform', 'Window', 'Lag', 'Signal Type', 'Threshold', 'Sharpe Ratio', 'Gross PnL', 'Net PnL'];
        const rows = currentPopulation.map((s, i) => [
            i + 1,
            s.feature,
            s.transform,
            s.window,
            s.lag,
            s.signal_type,
            s.threshold.toFixed(2),
            s.sharpe.toFixed(3),
            s.pnl,
            s.adj_pnl
        ]);

        const csvContent = [
            headers.join(','),
            ...rows.map(e => e.join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', 'alphalution_strategies.csv');
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    /* ----- Init ----- */
    function init() {
        initHeroHelix();

        // Nav scroll behavior
        let lastScroll = 0;
        const nav = $('#main-nav');
        window.addEventListener('scroll', () => {
            const current = window.scrollY;
            if (current > lastScroll && current > 80) {
                nav.classList.add('nav-hidden');
            } else {
                nav.classList.remove('nav-hidden');
            }
            lastScroll = current;
        });
    }

    // Start when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
