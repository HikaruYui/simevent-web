/* DATA & STATE DEMO (dipakai jelajah.html + peserta_page.html). Di Django: ganti dengan model + view (lihat django_peserta.py). */
const TODAY="2026-10-08";
const EV=[
{id:1,t:"Webinar Karier di Era AI untuk Fresh Graduate",k:"Webinar",tp:"Tech & AI",s:"live",f:"Online",loc:"Live via Zoom",d:"2026-10-11",o:"Dewi Anggraini",q:290,p:0},
{id:2,t:"Sosialisasi Beasiswa dan Program Magang Nasional",k:"Sosialisasi",tp:"Pendidikan & Riset",s:"soon",f:"Offline",loc:"Aula Rektorat",d:"2026-10-15",o:"Biro Kemahasiswaan",q:0,p:0},
{id:3,t:"Seminar Nasional Teknologi Informasi 2026",k:"Seminar",tp:"Tech & AI",s:"live",f:"Offline",loc:"Auditorium Unmul, Samarinda",d:"2026-10-18",o:"Dr. Rina Kartika, M.Kom",q:48,p:0},
{id:4,t:"Workshop UI/UX untuk Pemula",k:"Workshop",tp:"Desain & Produk",s:"soon",f:"Offline",loc:"Lab Komputer FKTI",d:"2026-10-24",o:"Andi Pratama",q:30,p:25000},
{id:5,t:"Konferensi Pendidikan & Riset Kalimantan",k:"Konferensi",tp:"Pendidikan & Riset",s:"soon",f:"Offline",loc:"Aula Utama, Samarinda",d:"2026-11-05",o:"Prof. Ahmad Fauzi",q:180,p:50000},
{id:6,t:"Workshop Analisis Data dengan Python",k:"Workshop",tp:"Tech & AI",s:"soon",f:"Online",loc:"Live via Zoom",d:"2026-11-12",o:"Sari Wulandari",q:75,p:35000},
{id:7,t:"Seminar Wirausaha Muda & Bisnis Digital",k:"Seminar",tp:"Bisnis & Finansial",s:"soon",f:"Offline",loc:"Gedung Serbaguna",d:"2026-11-20",o:"Budi Santoso",q:120,p:0},
{id:8,t:"Webinar Metodologi Penelitian Modern",k:"Webinar",tp:"Pendidikan & Riset",s:"done",f:"Online",loc:"Live via Zoom",d:"2026-10-02",o:"Dr. Lina Marlina",q:0,p:0}];
const SL={live:"Sedang Berlangsung",soon:"Akan Datang",done:"Selesai"};
const rp=n=>n?"Rp"+n.toLocaleString("id-ID"):"Gratis";
const fd=d=>new Date(d).toLocaleDateString("id-ID",{day:"numeric",month:"short",year:"numeric"});
let ST={regs:{}};try{ST=JSON.parse(localStorage.getItem("simevent_demo"))||ST}catch(e){}
const saveST=()=>{try{localStorage.setItem("simevent_demo",JSON.stringify(ST))}catch(e){}};
const isDone=e=>e.s==="done"||!!(ST.regs[e.id]&&ST.regs[e.id].done);
function daftarEvent(id){const e=EV.find(x=>x.id==id);if(ST.regs[id])return"sudah";ST.regs[id]={done:false,fb:null,cert:null};saveST();return"ok"}
