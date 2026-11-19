# CXAS Tracer Tests

Run everything from the repository root:

```bash
python3 -m unittest discover -s ces_tracing/tests -v
```

| File | What it covers |
| :--- | :--- |
| `test_transform.py` | Span conversion and ID rules, using small hand-written conversations. |
| `test_main.py` | Event handling, CES app resolution, idempotency guard, error handling. |
| `test_fixtures.py` | Golden-file tests: recorded conversations in, full expected trace out. |

## Fixtures

A fixture is a pair of files in `fixtures/`:

| File | Content |
| :--- | :--- |
| `conversation_<name>.json` | A scrubbed CES `GetConversation` response (the input). |
| `expected_trace_<name>.json` | The spans `convert_to_trace_spans()` produces for it, in Cloud Trace v2 JSON, with PII redaction on (the output). |

The expected trace contains the conversation-derived spans only. No Cloud Logging entries are
supplied, so audit log, incoming call and CES response log spans are not part of it.

| Fixture | Recorded from | Notable content |
| :--- | :--- | :--- |
| `callback_openapi` | A 10-turn voice conversation | `BeforeAgent` callbacks calling an OpenAPI tool directly with a propagated `traceparent`, `BeforeTool` callbacks, an LLM-started async tool, agent transfers, a failing OpenAPI call. |

## The three steps

| Step | Script | Reads | Writes |
| :--- | :--- | :--- | :--- |
| 1. Fetch | `fetch_conversation.py` | CES `GetConversation` | `fixtures/conversation_<name>.json` |
| 2. Transform | `make_fixture.py` | `fixtures/conversation_<name>.json` | `fixtures/expected_trace_<name>.json` |
| 3. Upload | `upload_fixture_trace.py` | `fixtures/expected_trace_<name>.json` | Cloud Trace |

```bash
python3 ces_tracing/tests/fetch_conversation.py <project> <location> <app> <conversation> --name <name>
python3 ces_tracing/tests/make_fixture.py <name>
python3 ces_tracing/tests/upload_fixture_trace.py <name> --project <trace-project>
```

### Example

Conversation `119y0lNKWz2SUCExu2xYYAYFw` of app `example-app` in location `eu` of project
`example-ces-project`, saved as fixture `example_call` and viewed in project
`example-trace-project`:

```bash
# 1. Fetch: writes ces_tracing/tests/fixtures/conversation_example_call.json (scrubbed)
python3 ces_tracing/tests/fetch_conversation.py \
  example-ces-project eu example-app 119y0lNKWz2SUCExu2xYYAYFw --name example_call

# 2. Transform: writes ces_tracing/tests/fixtures/expected_trace_example_call.json
python3 ces_tracing/tests/make_fixture.py example_call

# 3. Upload: sends that trace file to Cloud Trace and prints the trace ID
python3 ces_tracing/tests/upload_fixture_trace.py example_call --project example-trace-project
```

Add `--dry-run` to step 3 to see what would be sent without writing to Cloud Trace.

Only step 2 runs the tracer's transform (`transform.py`). Step 1 does not transform anything,
and step 3 uploads the file step 2 wrote without running the tracer or redacting anything.

Steps 1 and 3 call Google Cloud APIs. They authenticate with the active gcloud account
(`gcloud auth print-access-token`) by default; pass `--adc` to use Application Default
Credentials instead (`gcloud auth application-default print-access-token`). Both send the target
project as the quota project.

### 1. Fetch: `fetch_conversation.py`

Scrubs the `GetConversation` response of identifying values and writes it to
`fixtures/conversation_<name>.json`. A full resource name
(`projects/<p>/locations/<l>/apps/<a>/conversations/<c>`) can be passed in place of the four
arguments. Pass `--name` or `--output` (if both are given, `--output` takes precedence).

| Option | Effect |
| :--- | :--- |
| `--no-redact` | Write the raw API response without scrubbing. Scrubbing is **on by default**. |
| `--output <path>` | Write to this path instead of the fixtures directory. |
| `--force` | Replace an existing output file. |
| `--adc` | Authenticate with Application Default Credentials. |

Scrubbing replaces the project ID and number, phone numbers, IP addresses, telephony header
values, visitor IDs, URL hostnames and all dialogue text. Tool names, tool arguments and
responses, callback `stdout`, timings and tool call IDs are kept, so review the result before
committing.

The session ID is kept, because it is a random identifier. The trace ID is `MD5(session_id)`,
so the recorded `traceparent` values stay exactly as CXAS sent them.

> [!WARNING]
> With `--no-redact` the file is the raw API response: caller phone numbers, IP addresses,
> project IDs, and what was said. Do not commit it. Write it outside the repository with
> `--output`; `make_fixture.py <name> --raw <path>` scrubs such a file into a fixture later.

### 2. Transform: `make_fixture.py`

Runs the tracer's transform on `fixtures/conversation_<name>.json`, with PII redaction on (the
service default) and no Cloud Logging entries, and writes the resulting spans to
`fixtures/expected_trace_<name>.json` in Cloud Trace v2 JSON.

Run it again to regenerate the expected trace after an intended change to `transform.py`.
Review the diff: the file records what the transform does, not what it should do.

`--raw <path>` first scrubs a raw `GetConversation` response from outside the repository into
`fixtures/conversation_<name>.json`, then transforms it.

### 3. Upload: `upload_fixture_trace.py`

Sends `fixtures/expected_trace_<name>.json` to Cloud Trace (`traces:batchWrite`) and prints the
trace ID. Span names are retargeted to the given project. By default all timestamps are shifted
by one offset so the trace ends now, and a new random trace ID is used so repeated uploads do
not pile up on one trace. Span IDs, parent links, durations and attributes are never changed.

| Option | Effect |
| :--- | :--- |
| `--keep-times` | Upload the recorded timestamps as they are. |
| `--keep-trace-id` | Upload under the trace ID stored in the file. |
| `--dry-run` | Print what would be sent without calling the API. |
| `--adc` | Authenticate with Application Default Credentials. |

This writes real spans to the project. They cannot be deleted; they expire with Cloud Trace
retention. The identity used needs `cloudtrace.traces.patch` on the project.

## Adding a fixture to the test suite

After steps 1 and 2, add the fixture to `FIXTURES` in `test_fixtures.py`, with the number of
OpenAPI tool calls made directly by a callback with a `traceparent` argument (`0` if there are
none), then run the suite.

`test_fixtures.py` checks, for each registered fixture:

* the produced trace equals the expected trace;
* span IDs are unique;
* each callback-invoked OpenAPI tool span has the span ID from its `traceparent` and is parented
  under its `Callback` span.

It also scans **every** JSON file in `fixtures/`, registered or not, and fails on a phone number
outside the `+1555` test range or an IP address outside `192.0.2.0/24`. This catches most raw
responses left in the directory, but it does not prove that a file was scrubbed.
