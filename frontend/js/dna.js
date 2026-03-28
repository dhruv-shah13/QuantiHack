/* ============================================================
   DNA Helix — Canvas Animation Engine
   ============================================================ */

class DNAHelix {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');

        // Animation state
        this.phase = 0;
        this.mode = 'idle'; // idle | evolving | mutating | complete
        this.running = false;
        this.animationId = null;

        // Helix geometry
        this.amplitude = options.amplitude || 100;
        this.nodeCount = options.nodeCount || 30;
        this.verticalSpacing = options.verticalSpacing || null; // auto-calc if null
        this.speed = options.speed || 0.015;
        this.rotationSpeed = this.speed;

        // Visual
        this.nodeRadius = options.nodeRadius || 3;
        this.lineWidth = options.lineWidth || 1.5;
        this.glowIntensity = options.glowIntensity || 12;

        // Colors
        this.colors = {
            strand1: options.strand1Color || '#2e7d32',
            strand2: options.strand2Color || '#1b5e20',
            rung: options.rungColor || 'rgba(46, 125, 50, 0.12)',
            glow1: options.glow1Color || '#81c784',
            glow2: options.glow2Color || '#69f0ae',
            particle: options.particleColor || '#69f0ae',
            mutation: options.mutationColor || '#ff5252',
        };

        // Particles (for mutation effects)
        this.particles = [];
        this.burstParticles = [];

        // Mutation flash nodes
        this.mutatingNodes = new Set();
        this.mutationTimer = 0;

        // Resize handling
        this.resize();
        this._resizeHandler = () => this.resize();
        window.addEventListener('resize', this._resizeHandler);
    }

    resize() {
        const rect = this.canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.ctx.scale(dpr, dpr);
        this.width = rect.width;
        this.height = rect.height;
        this.centerX = this.width / 2;

        if (!this.verticalSpacing) {
            this.verticalSpacing = this.height / this.nodeCount;
        }
    }

    /* ----- State control ----- */
    setMode(mode) {
        this.mode = mode;
        switch (mode) {
            case 'evolving':
                this.rotationSpeed = 0.035;
                break;
            case 'mutating':
                this.rotationSpeed = 0.055;
                this._triggerMutation();
                break;
            case 'complete':
                this.rotationSpeed = 0.008;
                this.mutatingNodes.clear();
                break;
            default:
                this.rotationSpeed = 0.015;
                this.mutatingNodes.clear();
        }
    }

    _triggerMutation() {
        // Mark 3–5 random nodes as mutating
        this.mutatingNodes.clear();
        const count = 3 + Math.floor(Math.random() * 3);
        for (let i = 0; i < count; i++) {
            this.mutatingNodes.add(Math.floor(Math.random() * this.nodeCount));
        }
        // Spawn burst particles at mutation sites
        this.mutatingNodes.forEach(idx => {
            const y = idx * this.verticalSpacing + this.verticalSpacing / 2;
            const t = idx * 0.45 + this.phase;
            const x1 = this.centerX + this.amplitude * Math.cos(t);
            this._spawnBurst(x1, y, 12);
        });
        // Clear mutations after a short window
        this.mutationTimer = 40;
    }

    _spawnBurst(x, y, count) {
        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5;
            const speed = 1.5 + Math.random() * 2.5;
            this.burstParticles.push({
                x, y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                size: 1 + Math.random() * 2.5,
                life: 50 + Math.random() * 30,
                maxLife: 80,
                alpha: 1,
                color: Math.random() > 0.5 ? this.colors.particle : this.colors.mutation,
            });
        }
    }

    /* ----- Update logic ----- */
    update() {
        this.phase += this.rotationSpeed;

        // Update mutation timer
        if (this.mutationTimer > 0) {
            this.mutationTimer--;
            if (this.mutationTimer === 0 && this.mode === 'mutating') {
                this.setMode('evolving');
            }
        }

        // Ambient particles (floating specks)
        if (this.mode === 'evolving' || this.mode === 'mutating') {
            if (Math.random() < 0.15) {
                this.particles.push({
                    x: this.centerX + (Math.random() - 0.5) * this.amplitude * 3,
                    y: Math.random() * this.height,
                    vx: (Math.random() - 0.5) * 0.3,
                    vy: -0.3 - Math.random() * 0.5,
                    size: 0.5 + Math.random() * 1.5,
                    life: 60 + Math.random() * 60,
                    maxLife: 120,
                    alpha: 1,
                    color: this.colors.particle,
                });
            }
        }

        // Update ambient particles
        this.particles = this.particles.filter(p => {
            p.x += p.vx;
            p.y += p.vy;
            p.life--;
            p.alpha = p.life / p.maxLife;
            return p.life > 0;
        });

        // Update burst particles
        this.burstParticles = this.burstParticles.filter(p => {
            p.x += p.vx;
            p.y += p.vy;
            p.vx *= 0.96;
            p.vy *= 0.96;
            p.life--;
            p.alpha = p.life / p.maxLife;
            return p.life > 0;
        });
    }

    /* ----- Render ----- */
    draw() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.width, this.height);

        const points1 = [];
        const points2 = [];

        // Calculate helix points
        for (let i = 0; i <= this.nodeCount; i++) {
            const y = i * this.verticalSpacing;
            const t = i * 0.45 + this.phase;
            const x1 = this.centerX + this.amplitude * Math.cos(t);
            const z1 = Math.sin(t);
            const x2 = this.centerX + this.amplitude * Math.cos(t + Math.PI);
            const z2 = Math.sin(t + Math.PI);
            const isMutating = this.mutatingNodes.has(i);

            points1.push({ x: x1, y, z: z1, index: i, isMutating });
            points2.push({ x: x2, y, z: z2, index: i, isMutating });
        }

        // Draw rungs (base pairs) — back layer first
        for (let i = 0; i <= this.nodeCount; i++) {
            const p1 = points1[i];
            const p2 = points2[i];
            if (i % 2 !== 0) continue; // Draw every other rung for cleaner look

            const alpha = 0.06 + 0.06 * Math.abs(p1.z);
            const rungColor = p1.isMutating
                ? `rgba(255, 82, 82, ${alpha * 3})`
                : `rgba(124, 77, 255, ${alpha})`;

            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = rungColor;
            ctx.lineWidth = p1.isMutating ? 2 : 1;
            ctx.stroke();
        }

        // Draw strand curves
        this._drawStrandCurve(ctx, points1, this.colors.strand1, this.colors.glow1);
        this._drawStrandCurve(ctx, points2, this.colors.strand2, this.colors.glow2);

        // Draw nodes — sorted by z-depth for 3D
        const allPoints = [
            ...points1.map(p => ({ ...p, strand: 1 })),
            ...points2.map(p => ({ ...p, strand: 2 })),
        ].sort((a, b) => a.z - b.z);

        allPoints.forEach(p => {
            const depthFactor = (p.z + 1) / 2; // 0 (back) to 1 (front)
            const size = this.nodeRadius * (0.4 + 0.6 * depthFactor);
            const alpha = 0.25 + 0.75 * depthFactor;
            const color = p.strand === 1 ? this.colors.strand1 : this.colors.strand2;
            const mutColor = this.colors.mutation;

            ctx.save();
            if (depthFactor > 0.5) {
                ctx.shadowBlur = p.isMutating ? 20 : this.glowIntensity * depthFactor;
                ctx.shadowColor = p.isMutating ? mutColor : color;
            }

            ctx.beginPath();
            ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
            ctx.globalAlpha = alpha;
            ctx.fillStyle = p.isMutating ? mutColor : color;
            ctx.fill();
            ctx.globalAlpha = 1;
            ctx.restore();
        });

        // Draw particles
        [...this.particles, ...this.burstParticles].forEach(p => {
            ctx.save();
            ctx.globalAlpha = p.alpha * 0.7;
            ctx.shadowBlur = 6;
            ctx.shadowColor = p.color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.fill();
            ctx.restore();
        });
    }

    _drawStrandCurve(ctx, points, color, glowColor) {
        if (points.length < 2) return;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            const prev = points[i - 1];
            const curr = points[i];
            const cpx = (prev.x + curr.x) / 2;
            const cpy = (prev.y + curr.y) / 2;
            ctx.quadraticCurveTo(prev.x, prev.y, cpx, cpy);
        }
        const last = points[points.length - 1];
        ctx.lineTo(last.x, last.y);

        ctx.strokeStyle = color;
        ctx.lineWidth = this.lineWidth;
        ctx.globalAlpha = 0.4;
        ctx.shadowBlur = 8;
        ctx.shadowColor = glowColor;
        ctx.stroke();
        ctx.restore();
    }

    /* ----- Animation loop ----- */
    animate() {
        this.update();
        this.draw();
        if (this.running) {
            this.animationId = requestAnimationFrame(() => this.animate());
        }
    }

    start() {
        if (this.running) return;
        this.running = true;
        this.animate();
    }

    stop() {
        this.running = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    triggerMutation() {
        this._triggerMutation();
    }

    destroy() {
        this.stop();
        window.removeEventListener('resize', this._resizeHandler);
    }
}

// Export for use
window.DNAHelix = DNAHelix;
