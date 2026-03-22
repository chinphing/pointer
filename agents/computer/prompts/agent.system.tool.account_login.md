### account_login

Fill the **username** and/or **password** from locally stored credentials. **Never** put the real password or login **username** string in `tool_args`, `thoughts`, or `response`.

**Selecting the account (no profile id)**

- Required in `tool_args`: **`system`** — the product / site / app name (align with the **Saved login accounts** list injected in the same vision turn, or infer from the screenshot title, URL host, or branding).
- Optional: **`user_label`** — the short **account alias** for that system (same column in Settings → **Computer logins**). If the saved list shows **only one row** for that `system`, you may **omit `user_label`** and that row is used by default. If multiple rows exist for the same `system`, you **must** set **`user_label`** to disambiguate.
- **Natural language mapping:** When the user says e.g. “use **yyy** account on **XXX** system”, set **`system`** ≈ XXX and **`user_label`** ≈ yyy (match the injected list after normalize). When they say “log in to **XXX**” and there is only one saved account for XXX, omit **`user_label`**.
- **Rotate all accounts on one system:** Call **`account_login` multiple times** — same **`system`**, different **`user_label`**, in the **same order** as the injected list; use **wait** and the next screenshot between attempts to confirm logout or failure before the next account.

**Targets**

- Omit **`fill`**: fill **every** field for which you pass a target (`username_index` / `password_index`, or `username_coord` / `password_coord`). **At least one** target is required. If both username and password targets are provided, the tool fills **username first**, then **password** in **one** call.
- Set **`fill`** to **`username`** or **`password`**: fill **only** that field (you must pass the matching target; extra targets in `tool_args` are ignored). Legacy alias **`user_name`** is accepted and treated as **`username`**.

**Methods**

- **`fill_at_indices`** — Click by annotated **index**, clear field, paste from the resolved account.
  - Required: `goal`, **`system`**, and **at least one** of **`username_index`**, **`password_index`** (ints), unless **`fill`** is set — then the matching index is required.
- **`fill_at_coordinates`** — Same behaviour using **normalized** points (same scale as `mouse:click_at` / `composite_action:type_text_at`).
  - Required: `goal`, **`system`**, and **at least one** of **`username_coord`**, **`password_coord`**, each **`[x, y]`** (unless **`fill`** is set — then the matching coord is required).

**Behaviour**

1. Focus, **select-all + backspace** to clear, then paste from the stored row (content is not echoed in logs).
2. **Username and password fields:** confirm from the **next screenshot** in `thoughts` (password is usually masked).

**Hard rule:** Do not pass plaintext secrets under keys like `password`, `username`, `user_name`, `passwd`, `secret`, etc. in `tool_args`. Use **`system`** + optional **`user_label`** plus index/coord targets only. The **`fill`** parameter may be **`username`** or **`password`** to select a single field; that is **not** the same as passing a secret string.

**Do not** use `composite_action:type_text_*` for passwords. Use **account_login** for login fields.
