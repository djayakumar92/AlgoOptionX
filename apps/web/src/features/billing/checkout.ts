type CheckoutOptions = { key: string; order_id: string; amount: number; currency: string; name: string; description: string; handler: () => void; modal: { ondismiss: () => void } };
type CheckoutInstance = { open: () => void; on: (event: string, callback: () => void) => void };
declare global { interface Window { Razorpay?: new (options: CheckoutOptions) => CheckoutInstance } }
let loading: Promise<void> | null = null;
async function loadProvider() {
  if (window.Razorpay) return;
  if (!loading) loading = new Promise<void>((resolve,reject) => {
    const script = document.createElement('script'); script.src = 'https://checkout.razorpay.com/v1/checkout.js'; script.async = true; script.referrerPolicy='no-referrer';
    const timeout = window.setTimeout(() => { script.remove(); loading=null; reject(new Error('Sandbox checkout could not load. Reconcile the pending order before starting another attempt.')); },15000);
    script.onload = () => { window.clearTimeout(timeout); if(window.Razorpay)resolve();else{loading=null;reject(new Error('Checkout provider did not initialize.'));} };
    script.onerror = () => { window.clearTimeout(timeout);script.remove();loading=null;reject(new Error('Sandbox checkout is unavailable. The pending order is preserved.')); };
    document.head.append(script);
  });
  await loading;
}
export type SandboxCheckout = { intent_id:string; provider_order:string; amount_paise:number; currency:string; key_id:string; mode:string };
export async function openSandboxCheckout(value:SandboxCheckout,onStatus:(notice:string)=>void) {
  if(value.mode!=='sandbox'||!value.key_id.startsWith('rzp_test_')||value.currency!=='INR')throw new Error('Only explicitly configured test-mode checkout is supported.');
  await loadProvider();
  const checkout=new window.Razorpay!({key:value.key_id,order_id:value.provider_order,amount:value.amount_paise,currency:value.currency,name:'AlgoOptionX · TEST MODE',description:'Sandbox plan evaluation. No live payment.',handler:()=>onStatus('The provider reported payment completion. Credits appear only after server verification; refresh or reconcile this checkout.'),modal:{ondismiss:()=>onStatus('Checkout closed. Its pending order is preserved; reconcile it before starting another checkout.')}});
  checkout.on('payment.failed',()=>onStatus('The provider reported a failed attempt. Review provider status; no credits are granted by this browser callback.'));
  checkout.open();
}
