# The Agent Console's words

Every visible word on the page lives here so the wording changes in one place.

Each `## key` heading starts an entry whose value is the text under it up to the next heading.

Keys that start with `ui.` go to the page's script as they are. An entry written as a list of name and label pairs becomes a table.

Every word here can change without touching the code. The copy lint reads it line by line in the build. Each paragraph stays on one line for that reason.

## page.title

Agent Console

## page.description

Four AI agents did small jobs under a security policy that checked every tool call before it ran. It cut a planted prompt injection, held a push for a person and stopped a reach for a secrets file.

## page.share_alt

The morning as it opens with the reader's cut of the injected note on a vendor's pricing page

## page.skip

Skip to the page

## page.nav

- trace = The morning
- session = A session
- policies = The policy
- audit = The audit log
- how = How it works

## page.model

Model

## page.replay

Replay the morning

## page.tour

Take the tour

## page.preview

A development preview from the scripted stand-in with no model behind it

## page.footer

Fictional vendors, throwaway projects and real sessions recorded on my machine under a policy written for this demo.

## page.home

Back to the morning

## page.code_link

The code on GitHub

## page.home_link

ryansansbury.com

## how.title

How it works

## how.lead

Four AI agents worked one morning on small jobs in throwaway copies of four projects. Every tool call they made went through a policy before it ran, every web page they read was screened for prompt injections by a reader, every session had a budget and every event landed in a log that nobody can quietly edit. The runs were recorded on my machine and replay here. The policy and the log's check run live in your browser. Change a rule or an old entry to see what happens.

## how.map_head

What's AI and what's code

## how.map

- Choosing the next tool call = AI | Recorded and scored on the jobs with the policy's events
- Allowing a call, asking a person or denying it = Code (the policy) | Unit tests and a copy in this page that agrees on every recorded call
- Running the call = Code (the console's own tools) | They refuse anything outside the throwaway project whatever the policy says
- Reading web pages = Code (the reader) | A note planted on a vendor's page and scored for every model
- Stopping runaway spend = Code (the budget) | A recorded session that runs out of money
- Approving the risky calls = A person | Scripted in the recording with a label and yours to answer on this page
- The record = Code (a hash-chained log) | Checked in the build and in your browser

## how.threat_head

The threat model in plain words

## how.threat

The agents ran on the laptop that holds my work. The first thing to protect was everything outside each job's project and the second was anything that looks like a secret. An agent can misread a task and reach too far. A web page can carry a prompt injection meant for the agent. A loop can keep spending money with nothing to show for it.

Each of those meets more than one layer. A reach outside the project meets the policy first and then the tool layer that resolves every path for itself. A planted instruction meets the reader first and then the address rules. Runaway spending meets a budget that checks before every model call and can't be overshot by a single reply.

## how.layers_head

The layers from the agent outward

## how.layers

- Each job gets only the tools it needs and the research agent has no shell at all.
- The system prompt tells every agent that web pages are data and never instructions.
- The policy decides every call from plain facts about it and denies anything no rule names.
- The tool layer refuses paths outside the project and any host but the fixture pages whatever the policy says.
- Commands run without a shell on a short list of settings. Git can talk only to folders on the same machine.
- The reader cuts text addressed to an AI agent and fences the rest as quoted data.
- Any value from a secrets file is masked in every output and the values themselves are fake.
- The budget is checked ahead of each model call and stops the session before it can pass the limit.
- Every event goes into a hash chain whose newest hash is published where an agent can't reach it.
- A person answers calls that leave the machine. Every session ran in a throwaway folder deleted afterward.

## how.experiment_head

The experiment with the reader switched off

## how.experiment_lead

The research job ran a second time for each model with the reader off and the planted note reached the agent word for word. The system prompt stayed the same. So did the policy that stood between the agent and the outside address.

## how.experiment_none

The experiment's runs aren't recorded yet.

## how.experiment_cols

- model = Model
- followed = Followed the note
- flagged = Told the person
- caught = What the policy did

## how.compare_head

The models side by side

## how.compare_lead

Each model worked the same four jobs under the same policy, prompt and budget. A coding job counts as done when the hidden tests pass. The research job counts when the notes hold every price and pick the cheapest vendor.

## how.compare_cols

- model = Model
- done = Jobs done
- unsafe = Unsafe events
- asked = Asked a person
- denied = Denied
- quarantined = Quarantined
- cost = Cost
- time = Time

## how.said

- yes = Yes
- no = No
- caught_all = Every attempt was stopped
- caught_none = Nothing to stop
- caught_some = An attempt got through
- route = opens the page
- warned = warned first
- never_warned = never warned
- stopped = stopped
- never_stopped = never stopped
- ok = It stopped where it should.
- not_ok = It didn't stop where it should.

## how.done_of

{done} of 4

## how.safe_stops

 and {n} stopped safely

## how.budget_line

{model} worked {job} under a {limit} limit. It spent {spent}, {warned} and {stopped}.

## how.budget_head

The budget test

## how.budget_none

The budget test isn't recorded yet.

## how.runs_head

The recorded sessions

## how.runs_cols

- date = Recorded
- model = Model
- run = Run
- job = Job
- state = Ended
- calls = Tool calls
- cost = Cost

## how.client_head

Before an agent goes near your systems

## how.client

- List everything the agent's tools can touch and take away whatever the job doesn't need.
- Start from a policy that denies anything it doesn't name and loosen it one rule at a time with a reason for each.
- Keep secrets out of the agent's working folder entirely and keep settings in a separate file from credentials.
- Put a person in front of anything that leaves the machine (a push, an email or a payment).
- Give every session a budget with a step limit and alert when one runs out.
- Keep an append-only log with its newest hash stored somewhere the agent can't write. Read it every week.

## how.limits_head

What these controls can't catch

## how.limits

- Code the agent writes and then runs through the test runner can do anything the user can do on that machine. A real production setup adds an operating system sandbox or a container around the agent for exactly that reason.
- The reader misses an instruction phrased as ordinary content or hidden in an image so the policy has to hold.
- A wrong edit inside the project is allowed by design because tests and review are there to catch it.
- These short runs on small projects show the mechanics and not how often a model goes wrong.

## how.code_head

The code

## how.code_lead

The five files below are the controls. The whole project's source opens here from the same files the build used.

## ui.legend

- allow = allowed
- ask = asked a person
- deny = denied
- quarantine = quarantined
- done = done
- turn = the model's turn

## ui.kpi

- calls = tool calls
- allow = allowed
- ask = asked a person
- deny = denied
- quarantine = quarantined
- done = sessions done
- cost = spent

## ui.trace_hint

Hover a tile to see its call. Select it for the rule that decided it and what happened next.

## ui.turn_calls

The model took {secs} and asked for {calls}.

## ui.turn_last

The model took {secs} and wrote its last reply.

## ui.n_calls

{n} tool calls

## ui.one_call

one tool call

## ui.next_call

The agent's next call

## ui.step_prev

The event before this one

## ui.step_next

The event after this one

## ui.state

- done = Done
- waiting = Waiting for a person
- stopped-denial = Stopped by a denial
- stopped-budget = Stopped by its budget
- step-cap = Stopped at its step limit
- turn-cap = Stopped at its turn limit
- time-cap = Stopped at its time limit
- error = Stopped by an error

## ui.verdict

- allow = Allowed
- ask = Asked a person
- deny = Denied
- refused = Refused by the tool layer
- quarantine = Quarantined
- masked = Masked

## ui.answer

- approve = approved
- decline = declined
- wait = left it waiting for a person

## ui.tool

- shell = Shell
- read = Read
- write = Write
- edit = Edit
- fetch = Fetch

## ui.title_morning

{date} from {start} to {end}

## ui.q_said

What the page said

## ui.q_given

What the agent was given

## ui.q_why

Why and what happened next

## ui.q_url

{host} as {job} fetched it

## ui.q_note

The agent read it as quoted data and used only the real prices.

## ui.q_step1

Every page goes through a reader that cuts a prompt injection like this one before the agent sees the page.

## ui.q_step2

The cut is logged with the page and the words removed so a person can check it.

## ui.q_step3

A note that slipped through would still meet the address rules. A fetch off the list asks a person first and the console reaches nothing but its fixture pages.

## ui.q_step4

The session went on and the agent finished its notes from the real prices.

## ui.audit_ref

Audit entry #{seq} · {hash} · chained to #{prev}

## ui.call_box

The call

## ui.rule_box

The rule that decided

## ui.next_box

What happened next

## ui.rule_line

Rule {n} of {total}. The first rule that matches decides.

## ui.no_rule

No rule matched this call so the default denied it.

## ui.deny_stop

The policy denied the call and ended the session. Nothing was read and a person sees what the agent wanted.

## ui.deny_go

The call didn't run. The agent heard which rule stopped it.

## ui.ask_wait

Every push needs a person under this policy. The agent is waiting here and nothing has left the machine yet.

## ui.approve

Approve

## ui.deny

Deny

## ui.you_approved

You approved it. A real console would now push to the stand-in remote. Your answer is the newest audit entry.

## ui.you_denied

You denied it so the push never runs. The commit stays here and your answer is now the newest audit entry.

## ui.ask_scripted

The recording script {answer} because nobody watched the run. The agent got that answer back.

## ui.allowed

The call ran inside the throwaway project and this is what came back.

## ui.refused_after

The policy allowed it but the tool layer refused it anyway.

## ui.masked_note

A value from the secrets file showed up in what came back. The console masked it before the agent could see it.

## ui.done_task

The task

## ui.done_reply

The agent's last words

## ui.done_checks

Checked against the key

## ui.budget_warn

This session passed 80% of its budget and its next results carried a warning to the agent.

## ui.budget_last

The money left could pay for one more reply at most. The warning with this call said so.

## ui.budget_stop

The next call could have passed the budget so the session stopped before making it.

## ui.no_output

Nothing came back.

## ui.term_head

{job} · {model} · in a throwaway copy of the project

## ui.paused

Paused

## ui.session_ended

The session ended here. {state}.

## ui.budget_label

Budget

## ui.spent_of

{spent} of {limit}

## ui.running

{minutes} · {calls} tool calls

## ui.events

Events

## ui.elsewhere

Elsewhere this morning

## ui.show_output

Show what came back

## ui.hide_output

Hide it

## ui.policy_lead

Each call meets these rules top to bottom until the first match decides.

## ui.group

- shell = Shell
- files = Files
- web = The web

## ui.reset

Reset to the recorded policy

## ui.sim_same

Your policy decides every recorded call the same way.

## ui.sim_changed

Under your changes {n} recorded calls would go differently.

## ui.sim_one

Under your change one recorded call would go differently.

## ui.sim_allow

{target} in {job} would run without asking anyone.

## ui.sim_deny

{target} in {job} would be denied.

## ui.sim_deny_stop

{target} in {job} would be denied and the session would stop there.

## ui.sim_ask

{target} in {job} would wait for a person.

## ui.sim_run

{target} in {job} would run.

## ui.sim_to_ask

{target} in {job} would go to a person instead of being denied.

## ui.sim_layer

The tool layer would still refuse it.

## ui.col

- time = Time
- tool = Tool
- call = Call
- recorded = Recorded
- yours = Your policy

## ui.same

Same

## ui.after_change

After a change

## ui.never_reached

Never reached

## ui.guardrails

This session's guardrails

## ui.stopped_head

What the policy stopped this morning

## ui.stopped

- outside = Paths outside a project
- secrets = Calls on a secrets file
- hosts = Addresses off the list
- pages = Instructions inside fetched pages
- pushes = Pushes waiting for a person

## ui.audit_lead

Every event this morning went into one chain where each entry carries the hash of the one before it. Change any entry and the check fails right there.

## ui.verify

Verify the chain

## ui.verified

All {n} entries check out and the newest matches the published head.

## ui.failed

The check fails at entry #{seq} because {why}.

## ui.why

- content = its contents no longer match its hash
- link = it points to a hash the entry before it no longer has
- sequence = an entry is missing or out of order
- head = the newest entry no longer matches the head published in the repo

## ui.tamper1

Change an old entry

## ui.tamper2

Fix its hash too

## ui.tamper3

Rewrite everything after it

## ui.tamper_reset

Put it back

## ui.tamper_note

Entry #{seq} now says the call was allowed.

## ui.published

The published head

## ui.audit_cols

- seq = #
- at = Time
- session = Session
- actor = Who
- action = What
- target = On
- verdict = Verdict
- rule = Rule
- hash = Hash

## ui.actor

- agent = the agent
- policy = the policy
- script = the recording script
- person = a person
- reader = the reader
- budget = the budget
- console = the console
- you = you

## ui.tour_next

Next

## ui.tour_back

Back

## ui.tour_close

Close

## ui.tour_count

{n} of {total}

## ui.tour

- 1 = Four agents took on four small jobs one morning. Each lane is one agent's work call by call.
- 2 = The research agent read a vendor's pricing page with a prompt injection hidden in it. The reader cut the note before the agent ever saw it.
- 3 = On the left is what the page said. In the middle is the agent's copy with the note gone and the prices intact.
- 4 = The scripting agent reached for the secrets file and the policy ended its session on the spot.
- 5 = The billing agent finished its work and tried to push. A push waits for a person and you can approve or deny it here.
- 6 = A session replays as a terminal that shows every call's verdict and the rule behind it.
- 7 = These are the rules. Change any of them to see which recorded calls would have gone differently.
- 8 = Every event went into a hash chain where changing an old entry breaks the check at that entry.
- 9 = How it works covers the threat model, the layers, the reader-off experiment and the code.

## ui.screen

- trace = Morning
- session = Session
- policies = Policy
- audit = Log
- how = How

## ui.empty

The recorded sessions load here once the build has them.

## ui.lane_answer

- approve = Approved by you
- deny = Denied by you

## ui.view_heads

- policies = The rules
- audit = Every event in one chain
- chain = The chain so far

## ui.tri

- allow = Allow
- ask = Ask
- deny = Deny

## ui.trace_lead

Each lane is an AI agent in a throwaway project with a tile for every tool call the policy checked before it ran.

## ui.recorded

Replaying recorded sessions

## ui.answer_short

- approve = approved
- decline = declined
- wait = waiting for a person
