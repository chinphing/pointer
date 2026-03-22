import * as API from "/js/api.js";
import { store as notificationStore } from "/components/notifications/notification-store.js";

function toast(text, type = "info", timeout = 5000) {
  notificationStore.addFrontendToastOnly(type, text, "", timeout / 1000);
}

function rowKey(row) {
  const s = (row.system || "").trim().toLowerCase();
  const u = (row.user_label || "").trim().toLowerCase();
  return `${s}\0${u}`;
}

/** Register Alpine.data("computerCredentials") — call after Alpine is loaded. */
export function registerComputerCredentialsAlpine() {
  Alpine.data("computerCredentials", () => ({
    loaded: false,
    loading: false,
    saving: false,
    path: "",
    passwordPlaceholder: "****PSWD****",
    rows: [],
    msg: "",

    async init() {
      await this.load();
    },

    async load() {
      this.loading = true;
      this.msg = "";
      try {
        const r = await API.callJsonApi("computer_credentials_get", {});
        if (!r.success) {
          this.msg = r.error || "Load failed";
          toast(this.msg, "error");
          this.rows = [];
          return;
        }
        this.path = r.path || "";
        if (r.password_placeholder) {
          this.passwordPlaceholder = r.password_placeholder;
        }
        const list = Array.isArray(r.accounts) ? r.accounts : [];
        this.rows = list.map((a) => ({
          system: a.system || "",
          user_label: a.user_label || "",
          username: a.username || "",
          password: a.password || "",
          system_aliases: Array.isArray(a.system_aliases) ? [...a.system_aliases] : [],
          user_aliases: Array.isArray(a.user_aliases) ? [...a.user_aliases] : [],
        }));
      } catch (e) {
        this.msg = e.message || String(e);
        toast(this.msg, "error");
        this.rows = [];
      } finally {
        this.loading = false;
        this.loaded = true;
      }
    },

    addRow() {
      this.rows.push({
        system: "",
        user_label: "",
        username: "",
        password: "",
        system_aliases: [],
        user_aliases: [],
      });
    },

    removeRow(index) {
      this.rows.splice(index, 1);
    },

    async save() {
      const ph = this.passwordPlaceholder;
      const seen = new Set();
      const accounts = [];

      for (const row of this.rows) {
        const system = (row.system || "").trim();
        const ul = (row.user_label || "").trim();
        const un = (row.username || "").trim();
        const pw = row.password === undefined || row.password === null ? "" : row.password;

        if (!system) {
          if (ul || un || (pw && pw !== ph && String(pw).trim())) {
            toast("Each row with data must have a **system** name.", "error");
            return;
          }
          continue;
        }

        const rk = rowKey(row);
        if (seen.has(rk)) {
          toast(`Duplicate system + user_label: ${system} / ${ul || "(empty)"}`, "error");
          return;
        }
        seen.add(rk);

        const acc = {
          system,
          user_label: ul,
          username: row.username || "",
          password: pw,
        };
        if (row.system_aliases && row.system_aliases.length) {
          acc.system_aliases = row.system_aliases;
        }
        if (row.user_aliases && row.user_aliases.length) {
          acc.user_aliases = row.user_aliases;
        }
        accounts.push(acc);
      }

      this.saving = true;
      this.msg = "";
      try {
        const r = await API.callJsonApi("computer_credentials_set", { accounts });
        if (!r.success) {
          this.msg = r.error || "Save failed";
          toast(this.msg, "error");
          return;
        }
        toast("Computer login accounts saved.", "success");
        await this.load();
      } catch (e) {
        this.msg = e.message || String(e);
        toast(this.msg, "error");
      } finally {
        this.saving = false;
      }
    },
  }));
}
