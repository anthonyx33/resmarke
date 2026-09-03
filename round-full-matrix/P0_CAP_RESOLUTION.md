# P0 CAP RESOLUTION — FULL MATRIX (master engineer verification)

Flash stopped correctly. I verified the stop at code level. The `999999`
secret is **silently rejected** and the run needs **two** changes, not one.

## 1. What the code actually does

`supabase/functions/grade-image/index.ts`:

```ts
function sessionCap(): number {
  const value = Number(Deno.env.get("GRADE_SESSION_CAP") ?? DEFAULT_SESSION_CAP);
  return Number.isInteger(value) && value > 0 && value <= 10_000
    ? value : DEFAULT_SESSION_CAP;   // 999999 fails -> falls back to 40
}
```

`supabase/migrations/20260825000000_grade_cache.sql`:

```sql
effective_cap integer := greatest(1, least(p_cap, 10000));
-- on every call: session_cap = least(session_cap, effective_cap)
```

Consequences:

1. `GRADE_SESSION_CAP=999999` is invalid. It is clamped back to **40** on the
   server, on every request. Flash's `/40` reading was the live enforced cap,
   not a stale display.
2. The cap is stored **per grade session** in `grade_sessions.session_cap`
   and the SQL only ever **lowers** it (`least(...)`). The current tab's
   session row is permanently 40 — even after the secret is fixed, that
   session stays 40 forever.
3. The client derives the grade session id from **sessionStorage**
   (`resmarke:relab:grade-session`, per tab). A new tab = new session row.

## 2. Unblock (both steps, in order)

**Owner (terminal):**

```bash
supabase secrets set GRADE_SESSION_CAP=10000 --project-ref otzjqcnrabfbonjywlye
```

10000 is the maximum the function accepts and is 200x the matrix need
(44 grades + 1 verification + margin).

**Flash (operator):**

- Open a **fresh browser tab** of /relab (never reuse the current tab — its
  session row is locked at cap 40).
- Run P0 step 3 (the one verification grade, outside the matrix).
- Confirm the response `session_usage.cap == 10000` and the panel shows a
  `/10000`-style counter. If it shows 40 → STOP again.

## 3. What does NOT change

Matrix scope, 44 cells, 44 real g1 grades, seed `lab-ctla1`, marker codes,
ledger mechanics, stop conditions. All unchanged.
