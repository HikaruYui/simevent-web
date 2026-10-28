/* Adapter demo lama. Muat partials/demo_seed.html sebelum memakai skrip ini. */
const TODAY=window.SIMEVENT_DEMO.legacy_today;
const EV=window.SIMEVENT_DEMO.legacy_events;
const SL={live:"Sedang Berlangsung",soon:"Akan Datang",done:"Selesai"};
const rp=n=>n?"Rp"+n.toLocaleString("id-ID"):"Gratis";
const fd=d=>new Date(d).toLocaleDateString("id-ID",{day:"numeric",month:"short",year:"numeric"});
let ST={regs:{}};try{ST=JSON.parse(localStorage.getItem("simevent_demo"))||ST}catch(e){}
const saveST=()=>{try{localStorage.setItem("simevent_demo",JSON.stringify(ST))}catch(e){}};
const isDone=e=>e.s==="done"||!!(ST.regs[e.id]&&ST.regs[e.id].done);
function daftarEvent(id){const e=EV.find(x=>x.id==id);if(ST.regs[id])return"sudah";ST.regs[id]={done:false,fb:null,cert:null};saveST();return"ok"}
