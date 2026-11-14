import { I18nService, TPipe } from '../../services/i18n';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';

const API = environment.apiUrl + 'api/';
type Slot = 'id_front' | 'id_back' | 'selfie';

@Component({
  selector: 'app-verification',
  standalone: true,
  imports: [TPipe, CommonModule],
  templateUrl: './verification.html',
  styleUrl: './verification.css',
})
export class Verification implements OnInit, OnDestroy {
  private i18n = inject(I18nService);
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));

  loading = signal(true);
  latest = signal<any>(null);
  files = signal<Record<Slot, File | null>>({ id_front: null, id_back: null, selfie: null });
  previews = signal<Record<Slot, string | null>>({ id_front: null, id_back: null, selfie: null });
  sending = signal(false);
  slots: { id: Slot; label: string; hint: string; icon: string; capture: 'user' | 'environment' }[] = [
    { id: 'id_front', label: 'Front of ID', hint: 'All four corners visible, no glare', icon: 'badge', capture: 'environment' },
    { id: 'id_back', label: 'Back of ID', hint: 'Make sure the text is readable', icon: 'flip', capture: 'environment' },
    { id: 'selfie', label: 'Selfie', hint: 'Face the camera in good light', icon: 'face', capture: 'user' },
  ];

  status = computed(() => this.latest()?.status ?? 'none');
  ready = computed(() => Object.values(this.files()).every(Boolean));
  canSubmit = computed(() => this.status() !== 'approved' && this.status() !== 'pending');

  ngOnInit() {
    this.appBar.setTitle('ID verification');
    this.appBar.clearActions();
    if (this.browser) this.load();
  }
  ngOnDestroy() { Object.values(this.previews()).forEach((u) => u && URL.revokeObjectURL(u)); }

  load() {
    this.http.get<any>(API + 'verification/latest/').subscribe({
      next: (v) => { this.latest.set(v); this.loading.set(false); },
      error: () => { this.latest.set(null); this.loading.set(false); },
    });
  }

  pick(slot: Slot, ev: Event) {
    const f = (ev.target as HTMLInputElement).files?.[0];
    if (!f) return;
    if (f.size > 8 * 1024 * 1024) { this.snack.open(this.i18n.t('That photo is over 8 MB. Please take a smaller one.'), this.i18n.t('OK'), { duration: 4000 }); return; }
    const old = this.previews()[slot]; if (old) URL.revokeObjectURL(old);
    this.files.update((x) => ({ ...x, [slot]: f }));
    this.previews.update((x) => ({ ...x, [slot]: URL.createObjectURL(f) }));
  }

  submit() {
    if (!this.ready()) return;
    const fd = new FormData();
    (Object.entries(this.files()) as [Slot, File][]).forEach(([k, f]) => fd.append(k, f));
    this.sending.set(true);
    this.http.post<any>(API + 'verification/submit/', fd).subscribe({
      next: () => {
        this.sending.set(false);
        this.files.set({ id_front: null, id_back: null, selfie: null });
        this.previews.set({ id_front: null, id_back: null, selfie: null });
        this.snack.open(this.i18n.t('Submitted. We usually review IDs within 1 to 2 working days.'), this.i18n.t('OK'), { duration: 4500, panelClass: 'success-snackbar' });
        this.load();
      },
      error: (e) => {
        this.sending.set(false);
        this.snack.open(e?.error?.detail || this.i18n.t('Upload failed. Check your connection and try again.'), this.i18n.t('OK'), { duration: 4500, panelClass: 'error-snackbar' });
      },
    });
  }
}
