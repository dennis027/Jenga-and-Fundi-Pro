// "Install app" support (PWA). Canonical copy: frontend/design-system/install.ts
import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

@Injectable({ providedIn: 'root' })
export class InstallService {
  private prompt: any = null;
  canInstall = signal(false);

  constructor() {
    if (!isPlatformBrowser(inject(PLATFORM_ID))) return;
    window.addEventListener('beforeinstallprompt', (e: Event) => { e.preventDefault(); this.prompt = e; this.canInstall.set(true); });
    window.addEventListener('appinstalled', () => { this.prompt = null; this.canInstall.set(false); });
  }

  async install() {
    if (!this.prompt) return;
    this.prompt.prompt();
    await this.prompt.userChoice.catch(() => null);
    this.prompt = null;
    this.canInstall.set(false);
  }
}
