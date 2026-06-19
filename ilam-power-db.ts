/**
 * سامانه پایگاه داده مشترکین برق ایلام
 * Ilam Electric Power Distribution - Customer Database
 * اتصال به: eserv.bargh-ilam.ir
 */

export type DebtLevel = 0 | 1 | 2 | 3;
export type CustomerStatus = 'عادی' | 'هشدار' | 'اخطار نهایی' | 'قطع شده' | 'پرونده قضایی';
export type CallResult = 'پاسخگو بود' | 'اشغال' | 'عدم پاسخ' | 'شماره اشتباه' | 'قطع کرد';

export interface PaymentPromise {
  date: string;
  amount: number;
  promisedDate: string;
  fulfilled: boolean;
  notes: string;
}

export interface CallLog {
  date: string;
  result: CallResult;
  duration: number; // seconds
  notes: string;
  debtAtCall: number;
}

export interface IlamCustomer {
  customerId: string;      // شناسه اشتراک ۱۰ رقمی
  fullName: string;
  address: string;
  phoneNumber: string;
  debtAmount: number;      // ریال
  lastBillDate: string;
  consumptionAvg: number;  // kWh ماهانه
  paymentHistory: string[]; // 'بدحساب', 'منظم', 'اخطار کتبی' ...
  status: CustomerStatus;
  zone: string;            // محله / منطقه
  lastCallDate: string | null;
  callNotes: string;
  callLogs: CallLog[];
  paymentPromises: PaymentPromise[];
}

export interface CollectionStrategy {
  debtLevel: DebtLevel;
  tone: string;
  greeting: string;
  warningMessage: string;
  installmentOffer: string;
  escalationAction: string;
}

// ─── استراتژی‌های وصول بر اساس سطح بدهی ─────────────────────────────────────

export const COLLECTION_STRATEGIES: Record<DebtLevel, CollectionStrategy> = {
  0: {
    debtLevel: 0,
    tone: 'دوستانه و محترمانه',
    greeting: 'سلام وقت بخیر. از بخش امور مشترکین شرکت برق ایلام تماس می‌گیرم.',
    warningMessage: 'بدهی کمی داری، اگه هر وقت فرصت کردی پرداخت کنی خیلی ممنون می‌شیم.',
    installmentOffer: 'نیازی به قسط‌بندی نیست، یه پرداخت ساده کافیه.',
    escalationAction: 'ارسال پیامک یادآوری'
  },
  1: {
    debtLevel: 1,
    tone: 'محترمانه با هشدار ملایم',
    greeting: 'سلام. از واحد وصول مطالبات شرکت توزیع نیروی برق استان ایلام تماس می‌گیرم.',
    warningMessage: 'بدهی شما در حال انباشت شدن است و جریمه دیرکرد ماهانه ۲ درصد اضافه می‌شود.',
    installmentOffer: 'می‌تونیم بدهی رو به ۲ قسط تقسیم کنیم.',
    escalationAction: 'ارسال اخطار کتبی + تماس مجدد ظرف ۱ هفته'
  },
  2: {
    debtLevel: 2,
    tone: 'رسمی و هشداردهنده',
    greeting: 'سلام. از بخش وصول مطالبات شرکت توزیع نیروی برق استان ایلام، شهرستان ایلام تماس می‌گیرم.',
    warningMessage: 'بدهی معوقه شما در لیست قطع انشعاب قرار گرفته. طبق ماده ۲۴ قرارداد، انشعاب می‌تواند قطع شود.',
    installmentOffer: 'امکان قسط‌بندی تا ۴ ماه وجود دارد، اما باید امروز به دفتر بلوار معلم مراجعه کنید.',
    escalationAction: 'اعزام تیم قطع انشعاب + ارجاع به واحد حقوقی'
  },
  3: {
    debtLevel: 3,
    tone: 'قاطع و حقوقی',
    greeting: 'از واحد حقوقی شرکت توزیع نیروی برق استان ایلام تماس می‌گیرم.',
    warningMessage: 'پرونده بدهی شما به واحد حقوقی ارجاع داده شده و در صورت عدم پرداخت، اقدام قانونی صورت می‌گیرد.',
    installmentOffer: 'آخرین فرصت: پرداخت ۵۰٪ بدهی امروز و تنظیم قرارداد برای باقی.',
    escalationAction: 'طرح دعوا در مراجع قضایی'
  }
};

// ─── پایگاه داده محلی (IndexedDB-backed via localStorage) ───────────────────

const STORAGE_KEY = 'ilam_power_customers_db';
const CALL_LOGS_KEY = 'ilam_power_call_logs';

export class IlamPowerDB {

  private static getSampleCustomers(): IlamCustomer[] {
    return [
      {
        customerId: '1402050101',
        fullName: 'علی کریمی',
        address: 'ایلام، محله زرجاب، کوچه امام حسین، پلاک ۱۲',
        phoneNumber: '09183001001',
        debtAmount: 15_000_000,
        lastBillDate: '1403/03/15',
        consumptionAvg: 600,
        paymentHistory: ['بدحساب', 'اخطار کتبی'],
        status: 'اخطار نهایی',
        zone: 'زرجاب',
        lastCallDate: null,
        callNotes: '',
        callLogs: [],
        paymentPromises: []
      },
      {
        customerId: '1402050102',
        fullName: 'فاطمه محمدی',
        address: 'ایلام، شهرک بهشتی، فاز ۲، بلوک B، واحد ۱۴',
        phoneNumber: '09183001002',
        debtAmount: 3_200_000,
        lastBillDate: '1403/03/10',
        consumptionAvg: 350,
        paymentHistory: ['منظم', 'اخطار کتبی'],
        status: 'هشدار',
        zone: 'شهرک بهشتی',
        lastCallDate: null,
        callNotes: '',
        callLogs: [],
        paymentPromises: []
      },
      {
        customerId: '1402050103',
        fullName: 'حسن عباسی',
        address: 'ایلام، بلوار فرهنگیان، نبش کوچه ۵، پلاک ۳۸',
        phoneNumber: '09183001003',
        debtAmount: 45_000_000,
        lastBillDate: '1403/01/20',
        consumptionAvg: 1200,
        paymentHistory: ['بدحساب', 'اخطار کتبی', 'قطع قبلی', 'پرونده قضایی'],
        status: 'پرونده قضایی',
        zone: 'فرهنگیان',
        lastCallDate: null,
        callNotes: 'اعتراض به مبلغ دارد',
        callLogs: [],
        paymentPromises: []
      },
      {
        customerId: '1402050104',
        fullName: 'زهرا رستمی',
        address: 'ایلام، خیابان معلم، پلاک ۷۱',
        phoneNumber: '09183001004',
        debtAmount: 800_000,
        lastBillDate: '1403/03/18',
        consumptionAvg: 180,
        paymentHistory: ['منظم'],
        status: 'عادی',
        zone: 'مرکزی',
        lastCallDate: null,
        callNotes: '',
        callLogs: [],
        paymentPromises: []
      },
      {
        customerId: '1402050105',
        fullName: 'محمود قاسمی',
        address: 'ایلام، محله جمالوند، خیابان ۱۷ شهریور، پلاک ۲۲',
        phoneNumber: '09183001005',
        debtAmount: 7_600_000,
        lastBillDate: '1403/02/28',
        consumptionAvg: 500,
        paymentHistory: ['بدحساب'],
        status: 'اخطار نهایی',
        zone: 'جمالوند',
        lastCallDate: null,
        callNotes: 'گفته دو هفته دیگه پرداخت می‌کنه',
        callLogs: [],
        paymentPromises: []
      },
      {
        customerId: '1402050106',
        fullName: 'مریم امیری',
        address: 'ایلام، خیابان امام خمینی، کوچه گلستان، پلاک ۵',
        phoneNumber: '09183001006',
        debtAmount: 22_000_000,
        lastBillDate: '1403/01/15',
        consumptionAvg: 900,
        paymentHistory: ['بدحساب', 'اخطار کتبی', 'قطع قبلی'],
        status: 'قطع شده',
        zone: 'مرکزی',
        lastCallDate: null,
        callNotes: 'انشعاب قطع شده. منتظر پرداخت برای وصل مجدد',
        callLogs: [],
        paymentPromises: []
      },
      {
        customerId: '1402050107',
        fullName: 'داود حیدری',
        address: 'ایلام، شهرک ولیعصر، فاز ۱، خیابان سوم، پلاک ۱۸',
        phoneNumber: '09183001007',
        debtAmount: 1_500_000,
        lastBillDate: '1403/03/05',
        consumptionAvg: 250,
        paymentHistory: ['منظم'],
        status: 'هشدار',
        zone: 'ولیعصر',
        lastCallDate: null,
        callNotes: '',
        callLogs: [],
        paymentPromises: []
      },
      {
        customerId: '1402050108',
        fullName: 'نسرین کمالی',
        address: 'ایلام، محله آبشار، کوچه بهار، پلاک ۳',
        phoneNumber: '09183001008',
        debtAmount: 60_000_000,
        lastBillDate: '1402/10/01',
        consumptionAvg: 2000,
        paymentHistory: ['بدحساب', 'اخطار کتبی', 'قطع قبلی', 'پرونده قضایی', 'حکم دادگاه'],
        status: 'پرونده قضایی',
        zone: 'آبشار',
        lastCallDate: null,
        callNotes: 'وکیل دارد. فقط از طریق واحد حقوقی پیگیری شود',
        callLogs: [],
        paymentPromises: []
      }
    ];
  }

  static getAllCustomers(): IlamCustomer[] {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      const defaults = this.getSampleCustomers();
      localStorage.setItem(STORAGE_KEY, JSON.stringify(defaults));
      return defaults;
    }
    try {
      return JSON.parse(raw);
    } catch {
      return this.getSampleCustomers();
    }
  }

  static saveAllCustomers(customers: IlamCustomer[]) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(customers));
  }

  static getCustomerById(customerId: string): IlamCustomer | null {
    return this.getAllCustomers().find(c => c.customerId === customerId) || null;
  }

  static getCustomerByPhone(phone: string): IlamCustomer | null {
    const clean = phone.replace(/\D/g, '');
    return this.getAllCustomers().find(c => c.phoneNumber.replace(/\D/g, '') === clean) || null;
  }

  static searchCustomers(query: string): IlamCustomer[] {
    const q = query.trim().toLowerCase();
    return this.getAllCustomers().filter(c =>
      c.fullName.includes(q) ||
      c.customerId.includes(q) ||
      c.phoneNumber.includes(q) ||
      c.address.includes(q) ||
      c.zone.includes(q)
    );
  }

  static getCustomersByZone(zone: string): IlamCustomer[] {
    if (zone === 'همه' || !zone) return this.getAllCustomers();
    return this.getAllCustomers().filter(c => c.zone === zone);
  }

  static getDebtorsForCampaign(minDebt = 500_000): IlamCustomer[] {
    return this.getAllCustomers()
      .filter(c => c.debtAmount >= minDebt)
      .sort((a, b) => b.debtAmount - a.debtAmount);
  }

  /** تعیین سطح تشدید وصول بر اساس مبلغ بدهی و تاریخچه */
  static getDebtLevel(customer: IlamCustomer): DebtLevel {
    const debt = customer.debtAmount;
    const hasLegalRecord = customer.paymentHistory.includes('پرونده قضایی') || customer.status === 'پرونده قضایی';
    if (hasLegalRecord || debt >= 30_000_000) return 3;
    if (debt >= 5_000_000) return 2;
    if (debt >= 1_000_000) return 1;
    return 0;
  }

  static getStrategy(customer: IlamCustomer): CollectionStrategy {
    return COLLECTION_STRATEGIES[this.getDebtLevel(customer)];
  }

  /** ثبت وعده پرداخت */
  static registerPaymentPromise(
    customerId: string,
    amount: number,
    promisedDate: string,
    notes = ''
  ): boolean {
    const customers = this.getAllCustomers();
    const idx = customers.findIndex(c => c.customerId === customerId);
    if (idx === -1) return false;
    customers[idx].paymentPromises.push({
      date: new Date().toISOString(),
      amount,
      promisedDate,
      fulfilled: false,
      notes
    });
    customers[idx].callNotes = notes || customers[idx].callNotes;
    customers[idx].lastCallDate = new Date().toISOString();
    this.saveAllCustomers(customers);
    return true;
  }

  /** ثبت نتیجه تماس */
  static logCall(customerId: string, result: CallResult, duration: number, notes: string): boolean {
    const customers = this.getAllCustomers();
    const idx = customers.findIndex(c => c.customerId === customerId);
    if (idx === -1) return false;
    customers[idx].callLogs.push({
      date: new Date().toISOString(),
      result,
      duration,
      notes
    });
    customers[idx].lastCallDate = new Date().toISOString();
    customers[idx].callNotes = notes || customers[idx].callNotes;
    this.saveAllCustomers(customers);
    return true;
  }

  /** آمار کلی */
  static getStats(): {
    total: number;
    totalDebt: number;
    byStatus: Record<string, number>;
    byZone: Record<string, number>;
    callsMade: number;
    promisesReceived: number;
  } {
    const customers = this.getAllCustomers();
    const byStatus: Record<string, number> = {};
    const byZone: Record<string, number> = {};
    let totalDebt = 0;
    let callsMade = 0;
    let promisesReceived = 0;

    for (const c of customers) {
      totalDebt += c.debtAmount;
      byStatus[c.status] = (byStatus[c.status] || 0) + 1;
      byZone[c.zone] = (byZone[c.zone] || 0) + 1;
      callsMade += c.callLogs.length;
      promisesReceived += c.paymentPromises.length;
    }

    return { total: customers.length, totalDebt, byStatus, byZone, callsMade, promisesReceived };
  }

  /** فرمت ریال به تومان خوانا */
  static formatCurrency(rials: number): string {
    const tomans = Math.round(rials / 10);
    if (tomans >= 1_000_000) return `${(tomans / 1_000_000).toFixed(1)} میلیون تومان`;
    if (tomans >= 1_000) return `${(tomans / 1_000).toFixed(0)} هزار تومان`;
    return `${tomans.toLocaleString('fa-IR')} تومان`;
  }

  static getZones(): string[] {
    const zones = new Set(this.getAllCustomers().map(c => c.zone));
    return Array.from(zones);
  }
}
