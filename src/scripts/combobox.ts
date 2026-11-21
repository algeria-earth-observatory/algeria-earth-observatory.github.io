/**
 * Accessible searchable select (ARIA 1.2 combobox with a listbox popup).
 *
 * Keyboard: type to filter (accent-insensitive; matches name, code or Arabic name);
 * Down/Up move; Enter selects; Escape closes and restores; Home/End in the list;
 * Tab commits an exact match. The committed value is a stable code, never a name.
 */
export interface Option { value: string; label: string; search: string; hint?: string }

const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[''`-]/g, ' ').replace(/\s+/g, ' ').trim();
export const searchKey = (...parts: (string | undefined)[]) => fold(parts.filter(Boolean).join(' '));

export class Combobox {
  input: HTMLInputElement;
  list: HTMLUListElement;
  options: Option[] = [];
  value = '';
  private shown: Option[] = [];
  private active = -1;
  private onChange: (v: string) => void;

  constructor(input: HTMLInputElement, list: HTMLUListElement, onChange: (v: string) => void) {
    this.input = input; this.list = list; this.onChange = onChange;
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-controls', list.id);
    input.autocomplete = 'off';
    list.setAttribute('role', 'listbox');
    input.addEventListener('input', () => { this.filter(input.value); this.open(); });
    input.addEventListener('focus', () => input.select());
    input.addEventListener('click', () => { if (this.list.hidden) { this.filter(''); this.open(); } });
    input.addEventListener('keydown', (e) => this.key(e));
    input.addEventListener('blur', () => setTimeout(() => this.commitOnBlur(), 120));
    list.addEventListener('mousedown', (e) => e.preventDefault());
    list.addEventListener('click', (e) => {
      const li = (e.target as HTMLElement).closest('li[data-value]') as HTMLLIElement | null;
      if (li) this.choose(li.dataset.value!);
    });
  }

  setOptions(opts: Option[], keep = true) {
    this.options = opts;
    if (!keep || !opts.some((o) => o.value === this.value)) this.set('', false);
    else this.set(this.value, false);
  }

  set(v: string, notify = true) {
    const o = this.options.find((x) => x.value === v);
    this.value = o ? v : '';
    this.input.value = o ? o.label : '';
    this.input.removeAttribute('aria-invalid');
    if (notify) this.onChange(this.value);
  }

  private filter(q: string) {
    const f = fold(q);
    const words = f.split(' ').filter(Boolean);
    this.shown = words.length ? this.options.filter((o) => words.every((w) => o.search.includes(w))) : this.options.slice();
    // options whose code or a word of the name starts with the query come first (stable sort)
    if (words.length) {
      const rank = (o: Option) => (o.search.split(' ').some((w) => w.startsWith(words[0])) ? 0 : 1);
      this.shown.sort((a, b) => rank(a) - rank(b));
    }
    this.active = this.shown.length ? 0 : -1;
    this.render();
  }

  private render() {
    const id = this.list.id;
    this.list.innerHTML = this.shown.length
      ? this.shown.slice(0, 400).map((o, i) => `<li role="option" id="${id}-${i}" data-value="${o.value}" aria-selected="${i === this.active}" class="rdd-opt">${escapeHtml(o.label)}${o.hint ? `<span class="rdd-opt-hint">${escapeHtml(o.hint)}</span>` : ''}</li>`).join('')
      : `<li class="rdd-opt-empty" role="presentation">No match. Try the name without accents, or the code.</li>`;
    if (this.active >= 0) {
      this.input.setAttribute('aria-activedescendant', `${id}-${this.active}`);
      this.list.querySelector(`#${CSS.escape(`${id}-${this.active}`)}`)?.scrollIntoView({ block: 'nearest' });
    } else this.input.removeAttribute('aria-activedescendant');
  }

  private open() { this.list.hidden = false; this.input.setAttribute('aria-expanded', 'true'); }
  close() { this.list.hidden = true; this.input.setAttribute('aria-expanded', 'false'); this.input.removeAttribute('aria-activedescendant'); }

  private choose(v: string) { this.set(v); this.close(); }

  private key(e: KeyboardEvent) {
    const openList = !this.list.hidden;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (!openList) { this.filter(''); this.active = Math.max(0, this.shown.findIndex((o) => o.value === this.value)); this.open(); this.render(); }
        else { this.active = Math.min(this.shown.length - 1, this.active + 1); this.render(); }
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (openList) { this.active = Math.max(0, this.active - 1); this.render(); }
        break;
      case 'Home': case 'End':
        if (openList && this.shown.length) { e.preventDefault(); this.active = e.key === 'Home' ? 0 : this.shown.length - 1; this.render(); }
        break;
      case 'Enter':
        if (openList && this.active >= 0) { e.preventDefault(); this.choose(this.shown[this.active].value); }
        break;
      case 'Escape':
        if (openList) { e.preventDefault(); this.close(); this.set(this.value, false); }
        break;
      case 'Tab':
        if (openList && this.active >= 0 && this.input.value.trim()) this.choose(this.shown[this.active].value);
        else this.close();
        break;
    }
  }

  private commitOnBlur() {
    if (document.activeElement === this.input) return;
    this.close();
    const typed = fold(this.input.value);
    if (!typed) { this.input.value = this.options.find((o) => o.value === this.value)?.label ?? ''; return; }
    const exact = this.options.find((o) => fold(o.label) === typed || o.value === this.input.value.trim());
    if (exact && exact.value !== this.value) this.set(exact.value);
    else this.input.value = this.options.find((o) => o.value === this.value)?.label ?? '';
  }
}

export function escapeHtml(s: unknown) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
}
