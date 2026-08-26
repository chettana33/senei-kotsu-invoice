import fs from 'node:fs';
import crypto from 'node:crypto';
import vm from 'node:vm';

const baseFile='senei_kotsu_invoice_v13_3_reports.html';
const file='senei_kotsu_invoice_v13_4_aging_candidate.html';
const base=fs.readFileSync(baseFile,'utf8'),html=fs.readFileSync(file,'utf8');
const scripts=s=>[...s.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(m=>m[1]);
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const results=[];function check(name,ok,detail){results.push({status:ok?'PASS':'FAIL',name,detail});if(!ok)process.exitCode=1}
const bs=scripts(base),cs=scripts(html);
check('JavaScript syntax',cs.every((code,i)=>{try{new vm.Script(code,{filename:file+'#'+i});return true}catch{return false}}),'Both scripts compile');
check('Protected Invoice script',hash(bs[0])===hash(cs[0]),'Original Invoice/A4 script is byte-identical to V13.3');
check('Storage keys preserved',html.includes("'senei_invoice_history_v10'")&&html.includes("'senei_payment_records_v13'")&&html.includes("'senei_receipt_seq_v13'"),'No Aging Local Storage key added');
check('Read-only Aging',!html.match(/function seneiRenderAging\([\s\S]*?localStorage\.setItem/),'Aging render path does not write storage');
check('No inferred due date',html.includes("due=d.useDeposit?seneiAgingDate(d.depositDue):null")&&html.includes('ระบบจะแสดง “No Due Date”'),'Only enabled Deposit Due Date is used');
check('Aging exports',html.includes('function seneiExportAgingCSV()')&&html.includes("a.download='senei-aging-'"),'Aging CSV export present');
check('Customer summary',html.includes('id="agingCustomerBody"')&&html.includes('id="agingCustomerCount"'),'Customer outstanding aggregation present');

const day=86400000,asOf=new Date(Date.UTC(2026,6,14));
function bucket(due){if(!due)return 'No Due Date';const days=Math.floor((asOf-due)/day);if(days<0)return 'Not Due';if(days<=30)return '0–30 Days';if(days<=60)return '31–60 Days';if(days<=90)return '61–90 Days';return '90+ Days'}
check('Future bucket',bucket(new Date(Date.UTC(2026,6,20)))==='Not Due','Future Deposit Due is not overdue');
check('0–30 bucket',bucket(new Date(Date.UTC(2026,5,20)))==='0–30 Days','24 overdue days');
check('31–60 bucket',bucket(new Date(Date.UTC(2026,4,20)))==='31–60 Days','55 overdue days');
check('61–90 bucket',bucket(new Date(Date.UTC(2026,3,20)))==='61–90 Days','85 overdue days');
check('90+ bucket',bucket(new Date(Date.UTC(2026,2,1)))==='90+ Days','More than 90 overdue days');
check('No Due Date bucket',bucket(null)==='No Due Date','Missing due date is never guessed');

const pairs=['div','section','table','style','script'].map(tag=>[tag,(html.match(new RegExp('<'+tag+'(?:\\s|>)','gi'))||[]).length,(html.match(new RegExp('</'+tag+'>','gi'))||[]).length]);
check('HTML structure',pairs.every(([,a,b])=>a===b),pairs.map(([t,a,b])=>`${t}:${a}/${b}`).join(', '));
const output={runAt:new Date().toISOString(),file,summary:{passed:results.filter(r=>r.status==='PASS').length,failed:results.filter(r=>r.status==='FAIL').length},results};
fs.writeFileSync('aging_regression_results.json',JSON.stringify(output,null,2));console.log(JSON.stringify(output,null,2));
