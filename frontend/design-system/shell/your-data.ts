// "Your data": download everything / delete account. Canonical: frontend/design-system/shell/your-data.ts
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, ViewChild, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { environment } from '../../environments/environment';
import { AuthService } from '../services/auth';
import { I18nService, TPipe } from '../services/i18n';
import { saveBlob } from './ui';

@Component({
  selector: 'app-your-data',
  standalone: true,
  imports: [FormsModule, TPipe],
  template: `
  <section class="panel your-data">
    <div class="panel-head"><div><h2>{{ 'Your data' | t }}</h2><p>{{ 'Under the Data Protection Act you can get a copy of your data or close your account.' | t }}</p></div></div>
    <div class="panel-body yd-rows">
      <div class="yd-row">
        <span class="yd-icon"><span class="icon">download</span></span>
        <div class="grow"><strong>{{ 'Download my data' | t }}</strong><small>{{ 'Your profile, gigs, scores, applications and payments as a JSON file.' | t }}</small></div>
        <button class="btn outline sm" type="button" (click)="download()" [disabled]="busy()">{{ 'Download' | t }}</button>
      </div>
      <div class="yd-row">
        <span class="yd-icon danger"><span class="icon">person_off</span></span>
        <div class="grow"><strong>{{ 'Delete my account' | t }}</strong><small>{{ 'Erases your name, phone, ID number and photo. Verified work stays on contractors’ records as “Deleted user”.' | t }}</small></div>
        <button class="btn outline sm danger-text" type="button" (click)="dlg.showModal()">{{ 'Delete' | t }}</button>
      </div>
    </div>
  </section>
  <dialog class="modal" #dlg>
    <div class="modal-head"><div><h2>{{ 'Delete my account' | t }}</h2><p>{{ 'This cannot be undone.' | t }}</p></div>
      <button class="icon-btn" type="button" (click)="dlg.close()" [attr.aria-label]="'Close' | t"><span class="icon">close</span></button></div>
    <div class="modal-body">
      <div class="field"><label for="yd-pw">{{ 'Enter your password to confirm' | t }}</label>
        <input id="yd-pw" class="input" type="password" autocomplete="current-password" [ngModel]="password()" (ngModelChange)="password.set($event)"></div>
    </div>
    <div class="modal-foot">
      <button class="btn ghost" type="button" (click)="dlg.close()">{{ 'Cancel' | t }}</button>
      <button class="btn danger" type="button" (click)="remove()" [disabled]="!password() || busy()">{{ 'Delete permanently' | t }}</button>
    </div>
  </dialog>`,
  styles: [`
    .yd-rows { display: flex; flex-direction: column; gap: 14px; }
    .yd-row { display: flex; align-items: center; gap: 14px; }
    .yd-row .grow { flex: 1; min-width: 0; display: flex; flex-direction: column; }
    .yd-row small { color: var(--muted); font-size: .84rem; }
    .yd-icon { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; flex: none; background: var(--primary-soft); color: var(--primary); }
    .yd-icon.danger { background: var(--danger-soft); color: var(--danger); }
    .danger-text { color: var(--danger) !important; }
    .btn.danger { background: var(--danger); color: #fff; border-color: var(--danger); }
  `],
})
export class YourData {
  private http = inject(HttpClient);
  private auth = inject(AuthService);
  private router = inject(Router);
  private snack = inject(MatSnackBar);
  private i18n = inject(I18nService);
  @ViewChild('dlg') dlgRef!: ElementRef<HTMLDialogElement>;
  busy = signal(false);
  password = signal('');
  private api = environment.apiUrl + 'api/account/';

  download() {
    this.busy.set(true);
    this.http.get(this.api + 'export/', { responseType: 'blob' }).subscribe({
      next: (b) => { this.busy.set(false); saveBlob(b, 'my-data.json'); },
      error: () => { this.busy.set(false); this.snack.open(this.i18n.t('Could not download.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  remove() {
    this.busy.set(true);
    this.http.post(this.api + 'delete/', { password: this.password() }).subscribe({
      next: () => {
        this.dlgRef.nativeElement.close();
        this.snack.open(this.i18n.t('Your account was deleted.'), this.i18n.t('OK'), { duration: 5000 });
        const out = () => this.router.navigate(['/login']);
        this.auth.logout().subscribe({ next: out, error: out });
      },
      error: (e) => {
        this.busy.set(false);
        this.snack.open(e?.error?.detail || this.i18n.t('Could not delete the account.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' });
      },
    });
  }
}
