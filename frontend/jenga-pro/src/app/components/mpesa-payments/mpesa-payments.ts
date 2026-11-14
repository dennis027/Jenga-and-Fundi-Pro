import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { downloadCsv } from '../../shell/ui';

const API = environment.apiUrl + 'api/';

@Component({
  selector: 'app-mpesa-payments',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './mpesa-payments.html',
  styleUrl: './mpesa-payments.css',
})
export class MpesaPayments implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  @ViewChild('payDialog') dialog?: ElementRef<HTMLDialogElement>;

  loading = signal(true);
  tx = signal<any[]>([]);
  tab = signal<'all' | 'ok' | 'failed'>('all');
  q = signal('');
  sending = signal(false);
  sent = signal(false);
  form = { phone: '', amount: '' as string | number };

  ok = computed(() => this.tx().filter((t) => t.result_code === 0));
  failed = computed(() => this.tx().filter((t) => t.result_code !== 0));
  shown = computed(() => {
    const base = this.tab() === 'ok' ? this.ok() : this.tab() === 'failed' ? this.failed() : this.tx();
    const q = this.q().toLowerCase();
    return base.filter((t) => !q || `${t.mpesa_receipt_number} ${t.phone_number} ${t.amount}`.toLowerCase().includes(q));
  });
  totalPaid = computed(() => this.ok().reduce((s, t) => s + Number(t.amount || 0), 0));
  monthPaid = computed(() => {
    const n = new Date();
    return this.ok().filter((t) => { const d = new Date(t.transaction_date); return d.getMonth() === n.getMonth() && d.getFullYear() === n.getFullYear(); })
      .reduce((s, t) => s + Number(t.amount || 0), 0);
  });

  ngOnInit() {
    this.appBar.setTitle('M-Pesa payments');
    this.appBar.setActions([{ id: 'refresh', icon: 'refresh', ariaLabel: 'Refresh', onClick: () => this.load() }]);
    if (!this.browser) return;
    this.load();
    this.http.get<any>(API + 'user/').subscribe({ next: (u) => { if (u?.phone) this.form.phone = u.phone; } });
  }

  load() {
    this.http.get<any>(API + 'single-messages/').subscribe({
      next: (r) => { this.tx.set([...(r.transactions || [])].sort((a, b) => b.transaction_date.localeCompare(a.transaction_date))); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  normalise(p: string) {
    const d = (p || '').replace(/\D/g, '');
    return d.startsWith('254') ? d : d.startsWith('0') ? '254' + d.slice(1) : d.length === 9 ? '254' + d : d;
  }
  valid() { return /^2547\d{8}$|^2541\d{8}$/.test(this.normalise(this.form.phone)) && Number(this.form.amount) >= 1; }

  open() { this.sent.set(false); this.dialog?.nativeElement.showModal(); }
  close() { this.dialog?.nativeElement.close(); }

  pay() {
    if (!this.valid()) return;
    this.sending.set(true);
    this.http.post<any>(API + 'stk-new-push/', { phone_number: this.normalise(this.form.phone), amount: Number(this.form.amount) }).subscribe({
      next: (r) => {
        this.sending.set(false);
        if (r?.ResponseCode === '0' || r?.CheckoutRequestID) { this.sent.set(true); setTimeout(() => this.load(), 20000); }
        else this.snack.open(r?.errorMessage || r?.CustomerMessage || 'M-Pesa did not accept the request.', 'OK', { duration: 5000, panelClass: 'error-snackbar' });
      },
      error: () => { this.sending.set(false); this.snack.open('Could not reach M-Pesa. Try again in a moment.', 'OK', { duration: 5000, panelClass: 'error-snackbar' }); },
    });
  }

  exportCsv() {
    downloadCsv('mpesa-payments.csv', this.shown().map((t) => ({ date: t.transaction_date, receipt: t.mpesa_receipt_number, phone: t.phone_number,
      amount_ksh: t.amount, status: t.result_code === 0 ? 'successful' : 'failed', note: t.result_desc })));
  }
}
