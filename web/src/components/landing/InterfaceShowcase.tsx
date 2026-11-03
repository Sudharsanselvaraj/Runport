import React from 'react'
import { motion } from 'framer-motion'
import {
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  Cpu,
  ShieldCheck,
  Activity,
  Sliders,
  Database,
  BarChart2,
  Terminal,
} from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'

export const InterfaceShowcase: React.FC = () => {
  const content = LANDING_CONTENT.interfaceShowcase

  return (
    <section id="features" className="rp-showcase-section">
      <div className="rp-container">
        {/* Section Header */}
        <div className="rp-showcase-header">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <h2 className="rp-h2" style={{ maxWidth: '500px' }}>
              See the models.
              <br />
              <span style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Know what is real.</span>
            </h2>
          </motion.div>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="rp-body-muted"
            style={{ maxWidth: '440px' }}
          >
            {content.headingRight}
          </motion.p>
        </div>

        {/* 2-Column Grid */}
        <div className="rp-showcase-grid">
          {/* Left Feature Card */}
          <motion.div
            initial={{ opacity: 0, x: -24 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
            className="rp-card-left"
          >
            <span className="rp-pill-tag">{content.cardBadge}</span>
            <h3 className="rp-h3" style={{ marginBottom: '16px' }}>
              {content.cardTitle}
            </h3>
            <p className="rp-body-muted" style={{ lineHeight: 1.6 }}>
              {content.cardDescription}
            </p>

            <div style={{ marginTop: 'auto', paddingTop: '32px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '14px 16px',
                  borderRadius: '14px',
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <ShieldCheck size={20} style={{ color: '#10b981', flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#ffffff' }}>Strict Ground Truth</div>
                  <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.5)' }}>Human-verified annotations only</div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Right Product UI Mockup */}
          <motion.div
            initial={{ opacity: 0, x: 24 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="rp-mockup-frame"
          >
            <div className="rp-mockup-inner">
              {/* Mockup Sidebar */}
              <aside className="rp-mockup-sidebar">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingLeft: '8px' }}>
                    <img src="/assets/landing/runport-emblem.png" alt="Runport" width="18" height="18" />
                    <span style={{ fontSize: '13px', fontWeight: 600, letterSpacing: '0.04em', color: '#fff' }}>RUNPORT</span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        fontSize: '12px',
                        color: 'rgba(255, 255, 255, 0.6)',
                      }}
                    >
                      <Cpu size={14} />
                      <span>Model Roster</span>
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        fontSize: '12px',
                        background: 'rgba(255, 255, 255, 0.1)',
                        color: '#ffffff',
                        fontWeight: 500,
                      }}
                    >
                      <BarChart2 size={14} style={{ color: '#10b981' }} />
                      <span>Benchmark Run</span>
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        fontSize: '12px',
                        color: 'rgba(255, 255, 255, 0.6)',
                      }}
                    >
                      <Layers size={14} />
                      <span>Connectors</span>
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        fontSize: '12px',
                        color: 'rgba(255, 255, 255, 0.6)',
                      }}
                    >
                      <Database size={14} />
                      <span>Datasets</span>
                    </div>
                  </div>
                </div>

                {/* Sidebar footer status */}
                <div
                  style={{
                    padding: '12px',
                    borderRadius: '10px',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#10b981' }}>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} />
                    <span>Ledger WAL Active</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)', marginTop: '2px' }}>Cap: $5.00 · Spent: $0.00</div>
                </div>
              </aside>

              {/* Mockup Main View */}
              <main className="rp-mockup-main">
                {/* Search Bar */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 14px',
                    borderRadius: '10px',
                    background: 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    fontSize: '12px',
                    color: 'rgba(255, 255, 255, 0.4)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Search size={14} />
                    <span>Search models, datasets, trace events...</span>
                  </div>
                  <span style={{ fontSize: '11px', opacity: 0.5 }}>⌘K</span>
                </div>

                {/* Run Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Active Evaluation Plan
                    </div>
                    <div style={{ fontSize: '16px', fontWeight: 600, color: '#ffffff', marginTop: '2px' }}>
                      Ticket Intent Classifier Benchmark
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: '11px',
                      padding: '4px 10px',
                      borderRadius: '9999px',
                      background: 'rgba(16, 185, 129, 0.12)',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      color: '#10b981',
                      fontWeight: 500,
                    }}
                  >
                    PROVENANCE: REPLAYED
                  </span>
                </div>

                {/* Progress Bar */}
                <div
                  style={{
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    borderRadius: '12px',
                    padding: '16px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '8px' }}>
                    <span style={{ color: 'rgba(255, 255, 255, 0.8)' }}>Progress · TEST Split</span>
                    <span style={{ color: '#10b981', fontWeight: 600 }}>88% (44 / 50 cases)</span>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '9999px', overflow: 'hidden' }}>
                    <div style={{ width: '88%', height: '100%', background: '#10b981', borderRadius: '9999px' }} />
                  </div>
                </div>

                {/* 4 Stat Metrics Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                  <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                    <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)' }}>Accuracy</div>
                    <div style={{ fontSize: '18px', fontWeight: 600, color: '#ffffff', marginTop: '2px' }}>95.5%</div>
                    <div style={{ fontSize: '10px', color: '#10b981' }}>Wilson CI: [88.2%, 98.6%]</div>
                  </div>
                  <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                    <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)' }}>p90 Latency</div>
                    <div style={{ fontSize: '18px', fontWeight: 600, color: '#ffffff', marginTop: '2px' }}>110 ms</div>
                    <div style={{ fontSize: '10px', color: 'rgba(255, 255, 255, 0.4)' }}>p50: 92ms · p99: 145ms</div>
                  </div>
                  <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                    <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)' }}>Cost / 1k</div>
                    <div style={{ fontSize: '18px', fontWeight: 600, color: '#ffffff', marginTop: '2px' }}>$0.00</div>
                    <div style={{ fontSize: '10px', color: '#38bdf8' }}>Offline Replay Mode</div>
                  </div>
                  <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                    <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)' }}>Remaining Cap</div>
                    <div style={{ fontSize: '18px', fontWeight: 600, color: '#ffffff', marginTop: '2px' }}>$5.00</div>
                    <div style={{ fontSize: '10px', color: '#10b981' }}>0% total spent</div>
                  </div>
                </div>

                {/* Case rows */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Recent Case Evaluations
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid rgba(255, 255, 255, 0.05)',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <CheckCircle2 size={14} style={{ color: '#10b981' }} />
                      <span style={{ color: '#ffffff' }}>case-044: "How do I upgrade subscription tier?"</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ color: 'rgba(255, 255, 255, 0.5)' }}>Label: BILLING</span>
                      <span style={{ color: '#10b981' }}>Match</span>
                      <span style={{ color: 'rgba(255, 255, 255, 0.3)' }}>98ms</span>
                    </div>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid rgba(255, 255, 255, 0.05)',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <CheckCircle2 size={14} style={{ color: '#10b981' }} />
                      <span style={{ color: '#ffffff' }}>case-043: "500 server error on POST /v1/chat"</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ color: 'rgba(255, 255, 255, 0.5)' }}>Label: TECH_SUPPORT</span>
                      <span style={{ color: '#10b981' }}>Match</span>
                      <span style={{ color: 'rgba(255, 255, 255, 0.3)' }}>112ms</span>
                    </div>
                  </div>
                </div>
              </main>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
