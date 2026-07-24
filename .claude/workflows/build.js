export const meta = {
  name: 'build',
  description:
    'Resume the design/code/review loop on tickets that already exist in tickets/, skipping Product',
  whenToUse:
    'When tickets were already created (ahead of time, or left mid-pipeline from a prior run) and you want Design -> Build to run on them directly, without regenerating tickets from a request.',
  phases: [
    { title: 'Discover', detail: 'Read matching tickets from tickets/' },
    { title: 'Design', detail: 'One technical design per ticket still missing one', model: 'opus' },
    { title: 'Build', detail: 'Implement (sonnet) + review (opus) each ticket, looping until it passes' },
  ],
}

// Mirrors feature.js's role-adoption trick: .claude/agents/ only registers custom agentTypes at
// session startup, so every stage runs on `general-purpose` and adopts its role by reading the
// matching .claude/agents/<role>.md file, with the model tier passed explicitly. Keep in sync with
// feature.js if that file's roles/models change.
const ROLE_FILE = {
  design: '.claude/agents/design.md',
  'code-python': '.claude/agents/code-python.md',
  'code-sql': '.claude/agents/code-sql.md',
  'code-terraform': '.claude/agents/code-terraform.md',
  'pr-review': '.claude/agents/pr-review.md',
  documentation: '.claude/agents/documentation.md',
}
const ROLE_MODEL = {
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

const MAX_REVIEW_ROUNDS = 3

const CODE_ROLE = {
  python: 'code-python',
  sql: 'code-sql',
  terraform: 'code-terraform',
  docs: 'documentation',
}

const DISCOVER_SCHEMA = {
  type: 'object',
  required: ['tickets'],
  properties: {
    tickets: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'title', 'component', 'path', 'status'],
        properties: {
          id: { type: 'string', description: 'e.g. DANDER-10' },
          title: { type: 'string' },
          component: { type: 'string', enum: ['python', 'sql', 'terraform', 'docs'] },
          path: { type: 'string', description: 'tickets/DANDER-<n>-<slug>.md' },
          status: { type: 'string', enum: ['open', 'in-design', 'in-code', 'in-review', 'done'] },
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

// `args`: an array of ticket ids (e.g. ["DANDER-10", "DANDER-11"]) to target specific tickets
// regardless of status, or omitted/null to resume every ticket under tickets/ whose status is not
// already 'done'.
const requestedIds = Array.isArray(args) ? args.filter((x) => typeof x === 'string') : null

// ── 1) Discover: read existing ticket files instead of asking Product to write new ones ──
phase('Discover')
const discoverTask =
  requestedIds && requestedIds.length
    ? `Read the ticket files for these ids under tickets/: ${requestedIds.join(', ')}. For each, ` +
      `report its id, title, component, path, status, and depends_on exactly as found in its ` +
      `frontmatter. Do not modify any files.`
    : `List every ticket file under tickets/ (skip TEMPLATE.md and README.md) whose frontmatter ` +
      `status is NOT 'done'. For each, report its id, title, component, path, status, and ` +
      `depends_on exactly as found in its frontmatter. Do not modify any files.`
const discovered = await agent(discoverTask, {
  agentType: 'general-purpose',
  phase: 'Discover',
  schema: DISCOVER_SCHEMA,
})

const tickets = (discovered && discovered.tickets) || []
if (!tickets.length) {
  log('No matching tickets found to resume.')
  return { requestedIds, tickets: [] }
}
log(`Resuming ${tickets.length} ticket(s): ${tickets.map((t) => `${t.id}(${t.status})`).join(', ')}`)

// ── 2) Design: only for tickets that don't have one yet ────────────────
phase('Design')
const needsDesign = tickets.filter((t) => t.status === 'open' || t.status === 'in-design')
if (needsDesign.length) {
  await parallel(
    needsDesign.map((t) => () =>
      runAgent(
        'design',
        `Produce the technical design for ticket ${t.id} (${t.path}). Read the ticket, apply the ` +
          `steering files, write the design into the ticket's Design section, and set status in-code.`,
        { label: `design:${t.id}`, phase: 'Design', schema: DESIGN_SCHEMA }
      )
    )
  )
} else {
  log('No tickets need a design pass.')
}

// ── 3) Build: implement + review each non-done ticket SERIALLY, dependency order ──
phase('Build')
const results = []
for (const t of topoSort(tickets)) {
  if (t.status === 'done') {
    results.push({ id: t.id, component: t.component, passed: true, rounds: 0, skipped: true })
    continue
  }

  const codeRole = CODE_ROLE[t.component] || 'code-python'

  await runAgent(
    codeRole,
    `Implement ticket ${t.id} (${t.path}) per its Design section and acceptance criteria. Apply all ` +
      `steering files. Record Implementation Notes and set status in-review.`,
    { label: `code:${t.id}`, phase: 'Build' }
  )

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
log(`Build complete: ${passedCount}/${results.length} ticket(s) passed review.`)
return { requestedIds, results }
