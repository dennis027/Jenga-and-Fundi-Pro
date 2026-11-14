import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';

const API = environment.apiUrl + 'api/';

@Component({
  selector: 'app-mpesa',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './mpesa.html',
  styleUrl: './mpesa.css',
})
export class Mpesa implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private route = inject(ActivatedRoute);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  @ViewChild('uploadDialog') dialog?: ElementRef<HTMLDialogElement>;

  loading = signal(true);
  payments = signal<any[]>([]);
  file = signal<File | null>(null);
  preview = signal<string | null>(null);
  reading = signal(false);
  readNote = signal<string | null>(null);
  saving = signal(false);
  form = { transaction_code: '', amount: '' as string | number };

  total = computed(() => this.payments().reduce((s, p) => s + Number(p.amount || 0), 0));
  confirmed = computed(() => this.payments().filter((p) => p.is_confirmed).reduce((s, p) => s + Number(p.amount || 0), 0));
  thisMonth = computed(() => {
    const n = new Date();
    return this.payments().filter((p) => { const d = new Date(p.payment_date); return d.getMonth() === n.getMonth() && d.getFullYear() === n.getFullYear(); })
      .reduce((s, p) => s + Number(p.amount || 0), 0);
  });

  ngOnInit() {
    this.appBar.setTitle('Payments received');
    this.appBar.clearActions();
    if (!this.browser) return;
    this.load();
    if (this.route.snapshot.queryParamMap.get('upload')) setTimeout(() => this.open(), 300);
  }

  load() {
    this.http.get<any[]>(API + 'upload-payment/').subscribe({
      next: (p) => { this.payments.set(p); this.loading.set(false); }, error: () => this.loading.set(false),
    });
  }

  open() {
    this.file.set(null); this.preview.set(null); this.readNote.set(null);
    this.form = { transaction_code: '', amount: '' };
    this.dialog?.nativeElement.showModal();
  }
  close() { this.dialog?.nativeElement.close(); }

  pick(ev: Event) {
    const f = (ev.target as HTMLInputElement).files?.[0];
    if (!f) return;
    this.file.set(f);
    const old = this.preview(); if (old) URL.revokeObjectURL(old);
    this.preview.set(URL.createObjectURL(f));
    this.reading.set(true); this.readNote.set(null);
    const fd = new FormData(); fd.append('image', f);
    this.http.post<any>(API + 'extract-code/', fd).subscribe({
      next: (r) => {
        this.reading.set(false);
        if (r.transaction_code) this.form.transaction_code = r.transaction_code;
        if (r.amount) this.form.amount = r.amount;
        this.readNote.set(r.transaction_code ? 'We read the code and amount from your screenshot. Check them before saving.' : 'We could not read this screenshot. Type the M-Pesa code and amount.');
      },
      error: () => { this.reading.set(false); this.readNote.set('We could not read this screenshot. Type the M-Pesa code and amount.'); },
    });
  }

  valid() { return /^[A-Za-z0-9]{8,12}$/.test(this.form.transaction_code.trim()) && Number(this.form.amount) > 0; }

  save() {
    if (!this.valid()) return;
    const fd = new FormData();
    fd.append('transaction_code', this.form.transaction_code.trim());
    fd.append('amount', String(this.form.amount));
    if (this.file()) fd.append('screenshot', this.file()!);
    this.saving.set(true);
    this.http.post<any>(API + 'upload-payment/', fd).subscribe({
      next: (p) => { this.saving.set(false); this.close(); this.payments.update((l) => [p, ...l]);
        this.snack.open('Saved. It counts as income proof once confirmed.', 'OK', { duration: 3500, panelClass: 'success-snackbar' }); },
      error: (e) => { this.saving.set(false);
        this.snack.open(e?.error?.transaction_code?.[0] || 'Could not save this payment.', 'OK', { duration: 4500, panelClass: 'error-snackbar' }); },
    });
  }
}
