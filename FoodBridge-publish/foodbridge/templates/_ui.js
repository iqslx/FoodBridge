
// Presentation enhancements only. All workflows continue to use normal server forms.
document.querySelectorAll('.notice-close').forEach(button=>button.addEventListener('click',()=>button.closest('.notice').remove()));
document.querySelectorAll('input[type="password"]').forEach(input=>{
  const wrapper=document.createElement('div');wrapper.className='password-wrap';input.before(wrapper);wrapper.append(input);
  const button=document.createElement('button');button.type='button';button.className='password-toggle';button.textContent='Show';button.setAttribute('aria-label','Show '+(document.querySelector('label[for="'+input.id+'"]')?.textContent||'password').toLowerCase());button.setAttribute('aria-controls',input.id);button.setAttribute('aria-pressed','false');
  button.addEventListener('click',()=>{const visible=input.type==='password';input.type=visible?'text':'password';button.textContent=visible?'Hide':'Show';button.setAttribute('aria-pressed',String(visible));button.setAttribute('aria-label',(visible?'Hide ':'Show ')+(document.querySelector('label[for="'+input.id+'"]')?.textContent||'password').toLowerCase());});wrapper.append(button);
});
document.querySelectorAll('form[method="post"],form[method="POST"]').forEach(form=>{
 form.addEventListener('submit',()=>{if(!form.checkValidity())return;const button=form.querySelector('button.btn:not([type="button"]),input[type="submit"]');if(button){button.dataset.originalLabel=button.textContent;button.disabled=true;if(button.tagName==='BUTTON')button.textContent='Please wait…';button.setAttribute('aria-busy','true');}});
});
window.addEventListener('pageshow',()=>document.querySelectorAll('[data-original-label]').forEach(button=>{button.disabled=false;button.removeAttribute('aria-busy');button.textContent=button.dataset.originalLabel;delete button.dataset.originalLabel;}));

// Preserve the English ISO date format while allowing the mobile number keyboard.
document.querySelectorAll('input[name="expiry_date"]').forEach(input=>input.addEventListener('input',event=>{
 if(event.inputType?.startsWith('delete')||input.selectionStart!==input.value.length||!/^[0-9-]*$/.test(input.value))return;
 const digits=input.value.replace(/-/g,'').slice(0,8);
 input.value=digits.slice(0,4)+(digits.length>4?'-'+digits.slice(4,6):'')+(digits.length>6?'-'+digits.slice(6,8):'');
}));
