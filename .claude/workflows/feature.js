export const meta = {
  name: 'feature',
  description: 'Turn a plain-English feature request into tickets, then design, implement, and review each ticket until it passes review',
  whenToUse: 'When you have a new feature/change described in plain English and want the agent workforce to decompose, design, build, and review it end to end.',
  phases: [
    { title: 'Product', detail: 'Decompose the request into tickets', model: 'opus' },
    { title: 'Design', detail: 'One technical design per ticket', model: 'opus' },
    { title: 'Build', detail: 'Implement (sonnet) + review (opus) each ticket, looping until it passes' },
  ],
}

// ── Role adoption ─────────────────────────────────────────────────────
// Custom agents in .claude/agents/ only register at SESSION STARTUP, so a workflow launched in the
// same session (or in a headless/cron run) can't reference them by agentType. To stay portable,
// every stage runs on the built-in `general-purpose` agent and ADOPTS its role by reading the
// matching .claude/agents/<role>.md definition (single source of truth). The model tier that would
// come from the agent's frontmatter is passed explicitly here instead.
const ROLE_FILE = {
  product: '.claude/agents/product.md',
  design: '.claude/agents/design.md',
  'code-python': '.claude/agents/code-python.md',
  'code-sql': '.claude/agents/code-sql.md',
  'code-terraform': '.claude/agents/code-terraform.md',
  'pr-review': '.claude/agents/pr-review.md',
  documentation: '.claude/agents/documentation.md',
}
const ROLE_MODEL = {
  product: 'opus',
  design: 'opus',
  'pr-review': 'opus',
  'code-python': 'sonnet',
  'code-sql': 'sonnet',
  'code-terraform': 'sonnet',
  documentation: 'sonnet',
}

function runAgent(role, task, opts) {
  const options = opts || {}
  const prompt =
    `You are acting as the "${role}" agent for the Dander project. FIRST read ${ROLE_FILE[role]} and ` +
    `fully adopt the role, constraints, and steering files it specifies (read those too). THEN carry ` +
    `out this task exactly:\n\n${task}`
  return agent(prompt, {
    agentType: 'general-purpose',
    model: ROLE_MODEL[role],
    label: options.label,
    phase: options.phase,
    schema: options.schema,
  })
}

// The feature request arrives as `args` (a string, or {request: "..."}).
const request =
  typeof args === 'string' ? args : args && args.request ? args.request : ''

if (!request) {
  log('No feature request provided. Invoke with args: "<plain-English description>".')
  return { error: 'missing feature request' }
}

// How many review rounds before we give up looping a ticket back to code.
const MAX_REVIEW_ROUNDS = 3

// component -> which code role implements it
const CODE_ROLE = {
  python: 'code-python',
  sql: 'code-sql',
  terraform: 'code-terraform',
  docs: 'documentation',
}

const TICKETS_SCHEMA = {
  type: 'object',
  required: ['tickets'],
  properties: {
    tickets: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'title', 'component', 'path'],
        properties: {
          id: { type: 'string', description: 'e.g. DANDER-1' },
          title: { type: 'string' },
          component: { type: 'string', enum: ['python', 'sql', 'terraform', 'docs'] },
          path: { type: 'string', description: 'tickets/DANDER-<n>-<slug>.md' },
          depends_on: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}

// Order tickets so a ticket's dependencies build before it (depends_on = ticket ids).
// Cycle-safe: a ticket already being visited is treated as satisfied rather than looping.
function topoSort(items) {
  const byId = new Map(items.map((t) => [t.id, t]))
  const state = new Map() // id -> 'visiting' | 'done'
  const order = []
  const visit = (t) => {
    const s = state.get(t.id)
    if (s === 'done' || s === 'visiting') return
    state.set(t.id, 'visiting')
    for (const dep of t.depends_on || []) {
      const d = byId.get(dep)
      if (d) visit(d)
    }
    state.set(t.id, 'done')
    order.push(t)
  }
  for (const t of items) visit(t)
  return order
}

const DESIGN_SCHEMA = {
  type: 'object',
  required: ['ticket_id', 'approach'],
  properties: {
    ticket_id: { type: 'string' },
    approach: { type: 'string' },
    interfaces: { type: 'array', items: { type: 'string' } },
    files_to_touch: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}

const REVIEW_SCHEMA = {
  type: 'object',
  required: ['ticket_id', 'verdict', 'summary'],
  properties: {
    ticket_id: { type: 'string' },
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    summary: { type: 'string' },
    blocking_issues: { type: 'array', items: { type: 'string' } },
    addendum: { type: 'string', description: 'Concrete, numbered fixes; empty on PASS' },
  },
}

// ── 1) Product: decompose the request into ticket files ───────────────
phase('Product')
const product = await runAgent(
  'product',
  `A feature request from the user:\n\n${request}\n\n` +
    `Decompose it into the smallest set of independently-implementable tickets. Create each as a ` +
    `markdown file under tickets/ following tickets/TEMPLATE.md and tickets/README.md (status: open, ` +
    `with a correct component and acceptance criteria). Return the ticket list.`,
  { phase: 'Product', schema: TICKETS_SCHEMA }
)

const tickets = (product && product.tickets) || []
if (!tickets.length) {
  log('Product agent produced no tickets. Nothing to build.')
  return { request, tickets: [] }
}
log(`Product created ${tickets.length} ticket(s): ${tickets.map((t) => t.id).join(', ')}`)

// ── 2) Design: one design per ticket, concurrently (distinct files) ───
phase('Design')
await parallel(
  tickets.map((t) => () =>
    runAgent(
      'design',
      `Produce the technical design for ticket ${t.id} (${t.path}). Read the ticket, apply the ` +
        `steering files, write the design into the ticket's Design section, and set status in-code.`,
      { label: `design:${t.id}`, phase: 'Design', schema: DESIGN_SCHEMA }
    )
  )
)

// ── 3) Build: implement + review each ticket SERIALLY, in dependency order ──
// Serial so code agents don't collide on files and each review sees the latest code. Code runs on
// sonnet (cheaper, high-volume) against an approved design; the opus review gate is the safety net.
// (To parallelize later, run code agents with isolation: 'worktree' and merge between stages.)
phase('Build')
const results = []
for (const t of topoSort(tickets)) {
  const codeRole = CODE_ROLE[t.component] || 'code-python'

  // initial implementation
  await runAgent(
    codeRole,
    `Implement ticket ${t.id} (${t.path}) per its Design section and acceptance criteria. Apply all ` +
      `steering files. Record Implementation Notes and set status in-review.`,
    { label: `code:${t.id}`, phase: 'Build' }
  )

  // review → (fail → re-implement) loop
  let round = 0
  let verdict = null
  while (round < MAX_REVIEW_ROUNDS) {
    round++
    verdict = await runAgent(
      'pr-review',
      `Review ticket ${t.id} (${t.path}) against its acceptance criteria and the steering files. ` +
        `Inspect the actual changed code. PASS only if fully met with no blocking issues; otherwise ` +
        `FAIL with a concrete numbered addendum. Append to the Review Log and set status accordingly.`,
      { label: `review:${t.id}#${round}`, phase: 'Build', schema: REVIEW_SCHEMA }
    )

    if (!verdict || verdict.verdict === 'PASS') break

    await runAgent(
      codeRole,
      `Ticket ${t.id} (${t.path}) failed review. Address every item in this addendum, update ` +
        `Implementation Notes, and set status in-review:\n\n${verdict.addendum || verdict.summary}`,
      { label: `code:${t.id}#${round + 1}`, phase: 'Build' }
    )
  }

  const passed = !!verdict && verdict.verdict === 'PASS'
  results.push({ id: t.id, component: t.component, passed, rounds: round })
  log(`${t.id}: ${passed ? 'PASS' : 'not passed'} after ${round} review round(s).`)
}

const passedCount = results.filter((r) => r.passed).length
log(`Feature complete: ${passedCount}/${results.length} ticket(s) passed review.`)
return { request, results }
