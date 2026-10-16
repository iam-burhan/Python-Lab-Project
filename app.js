const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.12});
document.querySelectorAll('.reveal').forEach((el,i)=>{el.style.transitionDelay=(i%4)*70+'ms';io.observe(el)});
document.querySelectorAll('[data-count]').forEach(el=>{const t=parseFloat(el.dataset.count),s=el.dataset.suffix||'',t0=performance.now();
(function f(n){const p=Math.min((n-t0)/900,1);el.textContent=(t%1?(t*p).toFixed(1):Math.round(t*p))+s;if(p<1)requestAnimationFrame(f)})(t0)});
document.querySelectorAll('.tilt').forEach(c=>{c.addEventListener('mousemove',e=>{const r=c.getBoundingClientRect(),x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;
c.style.transform=`perspective(700px) rotateY(${x*8}deg) rotateX(${-y*8}deg) translateY(-4px)`});c.addEventListener('mouseleave',()=>c.style.transform='')});
setTimeout(()=>document.querySelectorAll('.toast').forEach(t=>t.remove()),3500);
addEventListener('mousemove',e=>{document.body.style.setProperty('--mx',e.clientX+'px');document.body.style.setProperty('--my',e.clientY+'px')});
document.querySelectorAll('.sw button').forEach(b=>b.onclick=()=>{document.documentElement.dataset.theme=b.dataset.t;try{localStorage.setItem('lp-theme',b.dataset.t)}catch(e){}});
