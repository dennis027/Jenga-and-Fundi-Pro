// gig-summary.component.ts

import { afterNextRender, Component, inject, signal, OnInit, OnDestroy, PLATFORM_ID, TemplateRef, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { Router } from '@angular/router';
import { AppBarService } from '../../services/app-bar-service';
import { GigServices } from '../../services/gig-services';
import { SharedImports } from '../../shared-imports/imports';
import regionsData from '../../../assets/JSON-Files/regions.json';
import { MatSnackBar } from '@angular/material/snack-bar';
import { forkJoin } from 'rxjs'; // ADD THIS


interface JobType {
  id: number;
  name: string;
}

interface Gig {
  id: number;
  job_type: number;
  client_name: string;
  client_phone: string;
  county: string;
  constituency: string;
  ward: string;
  start_date: string;
  duration_value: number;
  duration_unit: string;
  is_verified: boolean;
}

@Component({
  selector: 'app-gig-summary',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatIconModule,
    MatButtonModule,
    MatDialogModule,
    SharedImports
  ],
  templateUrl: './gig-summary.html',
  styleUrl: './gig-summary.css',
})
export class GigSummary implements OnInit, OnDestroy {
  @ViewChild('addGigDialog') addGigDialogTemplate!: TemplateRef<any>;
  
  isLoading = signal(true);
  gigs = signal<Gig[]>([]);
  isSubmitting = signal(false);
  
  gigForm!: FormGroup;
  dialogRef?: MatDialogRef<any>;
  regions = regionsData;

  private fb = inject(FormBuilder);
  private appBar = inject(AppBarService);
  private router = inject(Router);
  private gigServices = inject(GigServices);
  private platformId = inject(PLATFORM_ID);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);


  private showSuccess(message: string) {
    this.snackBar.open(message, 'Close', {
      duration: 3000,
      panelClass: ['success-snackbar'],
      horizontalPosition: 'right',
      verticalPosition: 'top',
    });
  }

  private showError(message: string) {
    this.snackBar.open(message, 'Close', {
      duration: 4000,
      panelClass: ['error-snackbar'],
      horizontalPosition: 'right',
      verticalPosition: 'top',
    });
  }

  userRelatedGigs: Gig[] = [];
  organizations: any[] = [];

  gigTypes: any[] = [];

  counties: string[] = [];
  constituencies: string[] = [];
  wards: string[] = [];
  selectedPhoneNumber: string = '';


  selectedCounty: string = '';
  selectedConstituency: string = '';
  selectedWard: string = '';

  

  // Job types map
  private jobTypesMap: Map<number, string> = new Map();
  private gigTypesMap: Map<number, string> = new Map();



  constructor() {
    afterNextRender(() => {
      // Any browser-only code
    });
  }

  ngOnInit(): void {
    this.appBar.setTitle('My Gigs');
    this.appBar.setBack(true);

    this.appBar.setActions([
      {
        id: 'add-gig',
        icon: 'add',
        ariaLabel: 'Add Gigs',
        onClick: () => {
          this.openAddGigDialog();
        },
      },
      {
        id: 'refresh',
        icon: 'refresh',
        ariaLabel: 'Refresh Gigs',
        onClick: () => {
          this.fetchGigs(); // This will now reload everything
        },
      }
    ]);

    // Initialize form
    this.initGigForm();

    if (isPlatformBrowser(this.platformId)) {
      this.loadAllData(); // CHANGED: Load all data together
    }

    this.fetchRegions();
    this.setupLocationListeners();
  }

  // NEW METHOD: Load all data in parallel
  private loadAllData(): void {
    this.isLoading.set(true);

    forkJoin({
      organizations: this.gigServices.getOrganizations(),
      gigTypes: this.gigServices.getGigTypes(),
      userGigs: this.gigServices.userRelatedGigs(),
      gigsAvailable: this.gigServices.getGigsAvailable()
    }).subscribe({
      next: (results) => {
        console.log('All data loaded:', results);

        // Set organizations
        this.organizations = results.organizations;

        // Set gig types and build map
        this.gigTypes = results.gigTypes;
        this.gigTypes.forEach(jt => {
          this.gigTypesMap.set(jt.id, jt.name);
          this.jobTypesMap.set(jt.id, jt.name);
        });

        // Set user gigs
        this.userRelatedGigs = results.userGigs;
        this.gigs.set([...this.userRelatedGigs]); // Update signal

        this.isLoading.set(false);
      },
      error: (error) => {
        console.error('Error loading data:', error);
        this.isLoading.set(false);
        
        if (error.status === 401) {
          this.router.navigate(['/login']);
        } else {
          this.showError('Failed to load gigs. Please try again.');
        }
      }
    });
  }

  // UPDATED: Simplified fetchGigs to just reload
  fetchGigs(): void {
    this.loadAllData();
  }

  // REMOVE THESE OLD METHODS - They're now handled by loadAllData()
  /*
  getOrganizations(): void { ... }
  getGigsAvailable(): void { ... }
  getGigType(): void { ... }
  getUserRelatedGigs(): void { ... }
  */

  fetchRegions() {
  }

  setupLocationListeners(): void {
    // Load counties from JSON - use county_name instead of county
    this.counties = this.regions.map((r: any) => r.county_name);

    // Disable child controls initially
    this.gigForm.get('constituency')?.disable();
    this.gigForm.get('ward')?.disable();

    // COUNTY → CONSTITUENCY
    this.gigForm.get('county')?.valueChanges.subscribe((county: string) => {
      this.constituencies = [];
      this.wards = [];

      this.gigForm.patchValue({
        constituency: '',
        ward: ''
      });

      if (!county) {
        this.gigForm.get('constituency')?.disable();
        this.gigForm.get('ward')?.disable();
        return;
      }

      // Find county data using county_name
      const countyData = this.regions.find(
        (r: any) => r.county_name === county
      );

      // Map constituencies using constituency_name
      this.constituencies = countyData
        ? countyData.constituencies.map((c: any) => c.constituency_name)
        : [];

      if (this.constituencies.length > 0) {
        this.gigForm.get('constituency')?.enable();
      }
      this.gigForm.get('ward')?.disable();
    });

    // CONSTITUENCY → WARD
    this.gigForm.get('constituency')?.valueChanges.subscribe((constituency: string) => {
      this.wards = [];
      this.gigForm.patchValue({ ward: '' });

      if (!constituency) {
        this.gigForm.get('ward')?.disable();
        return;
      }

      // Find county data using county_name
      const countyData = this.regions.find(
        (r: any) => r.county_name === this.gigForm.get('county')?.value
      );

      // Find constituency data using constituency_name
      const constituencyData = countyData?.constituencies.find(
        (c: any) => c.constituency_name === constituency
      );

      // Wards is already an array of strings in your JSON
      this.wards = constituencyData ? constituencyData.wards : [];

      if (this.wards.length > 0) {
        this.gigForm.get('ward')?.enable();
      }
    });
  }

  initGigForm(): void {
    this.gigForm = this.fb.group({
      job_type: ['', Validators.required],
      start_date: ['', Validators.required],
      duration_value: [null, [Validators.required, Validators.min(1)]],
      duration_unit: ['', Validators.required],
      organization:['', Validators.required],
    });
  }

  ngOnDestroy(): void {
    this.appBar.clearActions();
    if (this.dialogRef) {
      this.dialogRef.close();
    }
  }

  getJobTypeName(jobTypeId: number): string {
    return this.gigTypesMap.get(jobTypeId) || 'Unknown Job';
  }

  openAddGigDialog(): void {
    this.gigForm.reset({ organization: 15 });
    this.dialogRef = this.dialog.open(this.addGigDialogTemplate, {
      width: '600px',
      maxWidth: '95vw',
      maxHeight: '90vh',
      panelClass: 'gig-dialog',
      disableClose: false
    });

    this.dialogRef.afterClosed().subscribe(() => {
      this.isSubmitting.set(false);
    });
  }

  closeDialog(): void {
    if (this.dialogRef) {
      this.dialogRef.close();
    }
  }

  onSubmit(): void {
    if (this.gigForm.invalid) {
      this.gigForm.markAllAsTouched();
      return;
    }

    this.isSubmitting.set(true);
    const payload = this.gigForm.value;

    console.log('SUBMIT PAYLOAD', payload);

    // REAL API IMPLEMENTATION
    this.gigServices.addGig(payload).subscribe({
      next: (newGig) => {
        // Add to local array
        this.userRelatedGigs.push(newGig);
        
        // Update signal
        this.gigs.set([...this.userRelatedGigs]);
        
        this.isSubmitting.set(false);
        this.closeDialog();
        this.showSuccess('Gig added successfully!');
      },
      error: (error) => {
        console.error('Error adding gig:', error);
        this.isSubmitting.set(false);
        this.showError('Failed to add gig. Please try again.');
      }
    });
  }

  hasError(fieldName: string): boolean {
    const field = this.gigForm.get(fieldName);
    return !!(field && field.invalid && field.touched);
  }

  getErrorMessage(fieldName: string): string {
    const field = this.gigForm.get(fieldName);
    if (!field) return '';

    if (field.hasError('required')) {
      return 'This field is required';
    }
    if (field.hasError('min')) {
      return 'Value must be greater than 0';
    }
    if (field.hasError('pattern')) {
      return 'Please enter a valid 10-digit phone number';
    }
    return '';
  }

  getOrgDetails(event: Event) {
    const orgId = (event.target as HTMLSelectElement).value;
    console.log(orgId);
    const selectedOrg = this.organizations.find(org => org.id == orgId);
    this.selectedCounty = selectedOrg ? selectedOrg.county : '';
    this.selectedConstituency = selectedOrg ? selectedOrg.constituency : '';
    this.selectedWard = selectedOrg ? selectedOrg.ward : '';
    this.selectedPhoneNumber = selectedOrg ? selectedOrg.phone_number : '';
  }
}