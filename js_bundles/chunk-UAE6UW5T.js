import{e as p}from"./chunk-VUONRY3T.js";import{G as l}from"./chunk-VXYX7FLX.js";import{Z as s,ca as d,ra as c}from"./chunk-UJPPAIWO.js";var b=(()=>{class n{constructor(e,i){this.http=e,this.injector=i,this.locked=!1,this.plaidOpened=!1,this.overlayRendered=!1}isLocked(){return this.locked}storeReviewSession(e){e&&this.http.post(`/api/plaid/idv/review/complete/${encodeURIComponent(e)}`,{},{responseType:"text"}).subscribe({next:()=>{},error:()=>{}})}enforce(e){return e?.idvReview?(this.lock(e.idvLinkToken,!!e.idvRejected),!0):this.locked}lock(e,i=!1){if(this.locked)return;if(this.locked=!0,this.killIntercom(),i){this.renderOverlay(!0);return}this.openPlaidThenLock(e)||this.renderOverlay()}killIntercom(){try{let e=window.Intercom;typeof e=="function"&&(e("hide"),e("shutdown"))}catch{}try{let e=document.createElement("style");e.id="idv-review-hide-intercom",e.textContent='.intercom-lightweight-app, #intercom-container, .intercom-messenger-frame, .intercom-launcher, iframe[name^="intercom"] { display: none !important; }',document.head.appendChild(e)}catch{}}openPlaidThenLock(e){if(this.plaidOpened||!e)return!1;let i=window.Plaid;if(!i?.create)return!1;this.plaidOpened=!0;try{return i.create({token:e,onSuccess:(o,a)=>{this.storeReviewSession(a?.link_session_id),this.renderOverlay()},onExit:()=>this.logOff()}).open(),!0}catch{return!1}}logOff(){try{this.injector.get(p).forceLogout()}catch{try{localStorage.clear()}catch{}window.location.href="https://lucidtrading.com/dashboard/"}}renderOverlay(e=!1){if(this.overlayRendered||document.getElementById("idv-review-lock"))return;this.overlayRendered=!0,document.body.style.overflow="hidden";let i=t=>{t.preventDefault(),t.stopPropagation()};if(window.addEventListener("keydown",t=>{t.key==="F5"||(t.ctrlKey||t.metaKey)&&t.key.toLowerCase()==="r"||(t.preventDefault(),t.stopPropagation())},!0),window.addEventListener("contextmenu",i,!0),!document.getElementById("idv-review-lock-style")){let t=document.createElement("style");t.id="idv-review-lock-style",t.textContent="@keyframes idvReviewPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.85)}}@keyframes idvReviewRing{0%{box-shadow:0 0 0 0 rgba(48,214,138,.35)}70%{box-shadow:0 0 0 7px rgba(48,214,138,0)}100%{box-shadow:0 0 0 0 rgba(48,214,138,0)}}",document.head.appendChild(t)}let r=document.createElement("div");r.id="idv-review-lock",r.setAttribute("role","alertdialog"),r.setAttribute("aria-modal","true"),r.style.cssText=`
      position: fixed; inset: 0; width: 100vw; height: 100vh;
      background: linear-gradient(180deg, rgba(10,11,16,0.94) 0%, rgba(10,10,12,0.97) 100%);
      backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
      z-index: 2147483647; display: flex; align-items: center; justify-content: center;
      padding: 24px;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;let o=e?"239,68,68":"48,214,138",a=e?"&#9888;":"&#128274;",h="Account Under Review",u=e?"Your account was flagged for identity verification and placed under review. During that review, multiple items were found to be inconsistent.<br><br>For that reason, Lucid Trading is not able to offer our services to you at this time.<br><br>Due to the volume of applications we review, we are not able to provide individual detail on why a verification did not pass. This decision is final and is not subject to appeal or further review.":"Your identity verification has been submitted and your account is under review. Access to the dashboard is paused while this review is completed.",f=e?"":`
        <div style="
          display: inline-flex; align-items: center; gap: 9px;
          padding: 8px 16px; border-radius: 999px;
          background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
          font-size: 12.5px; color: rgba(255,255,255,0.60); font-weight: 500;
          letter-spacing: 0.2px;
        ">
          <span style="
            width: 8px; height: 8px; border-radius: 50%; background: #30d68a;
            animation: idvReviewPulse 2s infinite;
          "></span>
          Review in progress
        </div>`;r.innerHTML=`
      <div style="
        background: rgba(21,21,26,0.82); border-radius: 12px; padding: 48px 44px 44px;
        max-width: 468px; width: 100%; text-align: center;
        border: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 60px rgba(${o},0.06);
      ">
        <div style="
          width: 68px; height: 68px; margin: 0 auto 28px; border-radius: 50%;
          display: flex; align-items: center; justify-content: center; font-size: 30px;
          background: rgba(${o},0.10); border: 1px solid rgba(${o},0.22);
          ${e?"":"animation: idvReviewRing 2.4s infinite;"}
        ">${a}</div>
        <h2 style="
          color: rgba(255,255,255,0.92); font-size: 23px; font-weight: 700;
          letter-spacing: -0.02em; margin: 0 0 16px; line-height: 1.3;
        ">${h}</h2>
        <p style="
          color: rgba(255,255,255,0.60); font-size: 15px; line-height: 1.75;
          letter-spacing: 0.1px; margin: 0 auto 30px; max-width: 360px;
        ">
          ${u}
        </p>
        ${f}
      </div>
    `,["click","mousedown","mouseup","dblclick","wheel","touchstart","touchmove"].forEach(t=>r.addEventListener(t,i,{passive:!1})),document.body.appendChild(r)}static{this.\u0275fac=function(i){return new(i||n)(d(l),d(c))}}static{this.\u0275prov=s({token:n,factory:n.\u0275fac,providedIn:"root"})}}return n})();export{b as a};
