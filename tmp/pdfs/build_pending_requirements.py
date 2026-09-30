from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from xml.sax.saxutils import escape

OUT=Path('output/pdf/FORESIGHT_Pending_Project_Requirements.pdf')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleX',fontName='Helvetica-Bold',fontSize=25,leading=29,textColor=colors.HexColor('#152D43'),spaceAfter=12))
styles.add(ParagraphStyle(name='SubX',fontName='Helvetica',fontSize=11,leading=16,textColor=colors.HexColor('#526578'),spaceAfter=12))
styles.add(ParagraphStyle(name='SectionX',fontName='Helvetica-Bold',fontSize=17,leading=22,textColor=colors.HexColor('#152D43'),spaceAfter=13))
styles.add(ParagraphStyle(name='TaskX',fontName='Helvetica-Bold',fontSize=11,leading=15,textColor=colors.HexColor('#173F52'),spaceAfter=5))
styles.add(ParagraphStyle(name='BodyX',fontName='Helvetica',fontSize=9.7,leading=14,spaceAfter=5))
styles.add(ParagraphStyle(name='SmallX',fontName='Helvetica',fontSize=8.2,leading=11.5,textColor=colors.HexColor('#586776'),spaceAfter=7))
styles.add(ParagraphStyle(name='NoteX',fontName='Helvetica',fontSize=9.3,leading=13.5,backColor=colors.HexColor('#EFF5F7'),borderPadding=9,spaceBefore=7,spaceAfter=15))
story=[]
def p(text,style='BodyX'): return Paragraph(text,styles[style])
def add(text,style='BodyX'):story.append(p(text,style))
def task(n,title,status,work,done,ref):
 story.append(KeepTogether([p(f'{n:02d}  {title}','TaskX'),p(f'<b>{status}.</b> {work}'),p(f'<b>Done when:</b> {done}'),p(f'Brief: {ref}','SmallX'),Spacer(1,7)]))
def page(title,subtitle):
 story.append(PageBreak());add(title,'SectionX');add(subtitle,'SubX')
def footer(c,d):
 w,h=A4;c.setStrokeColor(colors.HexColor('#D9E3E9'));c.line(42,44,w-42,44)
 c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#657787'));c.drawString(42,30,'FORESIGHT | Pending project work | Group checklist')
 c.drawRightString(w-42,30,f'{d.page} / 4')

add('PROJECT FORESIGHT','SmallX')
add('Pending project\nrequirements'.replace('\n','<br/>'),'TitleX')
add('Group work checklist | Reviewed 30 September 2026','SubX')
add('<b>Scope:</b> unfinished implementation, analysis and project documentation. Hosting, public URLs, demo video, submission forms and submission administration are excluded. The EDA memo and executive readout remain because they are core project deliverables (D2 and D7).','NoteX')
add('1. Data foundation and analysis','SectionX')
task(1,'Complete four-table ingestion','Partial','Obtain the supplied SKU master, calendar and inventory snapshots. Join them to sales with consistent date/SKU keys. Only the sales CSV is currently loaded.','All four extracts feed one analysis-ready dataset through the pipeline. Missing source extracts must come from the project provider.','D1.1; Sections 05 and 09')
task(2,'Implement cleaning and document decisions','Partial','Add coded handling for missing values, duplicate keys, invalid types and inconsistent labels. Validate joins and record what was changed and why. Current code mainly parses dates and sorts rows.','The pipeline validates/cleans inputs reproducibly and emits a data-quality summary with treatment counts and rationale.','D1.2-D1.4')
task(3,'Finish EDA and the insight memo','Partial','Add explicit top-mover and dead-stock analysis. Consolidate existing trend, seasonality and promotion findings into a readable data-quality/EDA memo with at least three operational insights.','The memo covers data issues and handling, trend, seasonality, top movers and dead stock, with labelled charts and practical actions.','D2.1-D2.4')
add('<b>Suggested owner:</b> Data / EDA team &nbsp;&nbsp; <b>Dependency:</b> obtain the three missing extracts first.','NoteX')

page('2. Forecasting and validation','Suggested owner: Forecasting team | Complete after the data foundation')
task(4,'Produce weekly SKU forecasts','Partial','Add weekly forecast outputs and weekly evaluation for a clearly defined horizon. Current output is daily predictions for 30 days.','Each SKU has weekly demand predictions with week dates and a documented horizon. Daily forecasts may be aggregated consistently; 6-8 weeks is an example in the brief, not a fixed requirement.','D3.1; Section 4.2')
task(5,'Retrain at each backtest origin','Partial','The current three-window evaluation updates input history but reuses one fitted model. Implement repeated training using only records preceding each forecast origin.','Rolling-origin results report model and seasonal-naive WAPE on matching folds/horizons, with bias and the final model-selection rationale.','D3.3; Appendix B')
task(6,'Use forecast-origin-valid inputs','Needs hardening','Backtests use the last price in the complete dataset. Replace this with price known at each origin or a documented advance price plan. Use promotion plans only when known in advance.','Changing future-only prices cannot alter earlier-origin inputs. Current prices are constant per SKU, so this is a latent risk, not an observed distortion of the existing scores.','D3.4')
task(7,'Correct uncertainty labels and add baseline curve','Correction needed','The band labelled 95% uses plus/minus 1.6449 error standard deviations, approximately a 90% central normal interval. The forecast chart also lacks the seasonal-naive curve.','The interval label matches its method (about 1.96 for a nominal central 95% normal interval), assumptions are stated, and actual, baseline and model curves appear together. Empirical calibration is a stretch goal.','Section 7.2; accuracy of existing output')
add('<b>Related safeguards from Section 16:</b> add a category-based fallback and low-confidence flag for sparse/new SKUs; compare forecasts with and without planned promotions. Both are currently absent.','NoteX')
add('<b>Evidence:</b> src/forecast.py; run_pipeline.py; app/streamlit_app.py. Saved WAPE comparisons exist, but this review did not independently reproduce training because the local OpenMP dependency was missing.','SmallX')

page('3. Inventory risk and dashboard','Suggested owners: Risk logic team and dashboard team')
task(8,'Use supplied inventory positions and costs','Partial','Replace generated stock, lead time and unit cost with supplied extracts. Include on-order units and calculate demand over each SKU\'s lead time from the forecast.','Risk reflects snapshot on-hand plus on-order stock and a documented lead-time/safety-stock rule. Financial calculations use supported costs and explicitly identified INR units.','D4.1-D4.2; Section 8.1')
task(9,'Implement all four risk quadrants','Missing','Create the stockout-versus-overstock decision grid, sized by revenue at stake. Add Reorder now, Markdown/clear, Watch/volatile and Healthy outcomes; current exclusive flags cannot express high risk on both axes.','Every SKU maps to a quadrant with a consistent explanation, action and financial exposure.','D4.4; Section 8.2')
task(10,'Complete and reconcile action recommendations','Partial','Add markdown/clear guidance for excess stock. Resolve positive recommended orders alongside "No action" for SKU001, SKU026 and SKU027 (96, 130 and 135 units in saved outputs).','Order quantity, action text and suggested spend agree, or clearly distinguish optional target replenishment from orders required now.','D4.2; D5.2; observed consistency defect')
task(11,'Add category filtering and empty/error states','Partial','Add a product-category filter using SKU master data; ABC class is not product category. Show a clear message when filters match no rows and handle missing or malformed input files gracefully.','Category/SKU views, risk flags and prioritised reorder/clearance lists are usable; empty results and invalid data show helpful messages without crashes.','D5.1-D5.4')
task(12,'Validate the usefulness of risk flags','Not demonstrated','Compare historical flags with subsequent stockout/overstock outcomes where the supplied snapshots support this. State limitations when observed outcomes are unavailable.','Risk precision or another justified outcome check is reported transparently, with no invented validation labels.','Section 3.2 success metrics')

page('4. Local readiness and project reports','Suggested owners: Integration team and analysis/documentation team')
task(13,'Document and validate local scoring','Partial','Document accepted SKU inputs and forecast/risk outputs, with an example. Handle unknown SKUs and missing/invalid data cleanly. This can be implemented through the dashboard; a separate FastAPI service is not required.','A teammate can obtain forecast plus risk for a valid SKU locally and receives a helpful error for bad input.','D6.2-D6.4 only; hosting excluded')
task(14,'Make the full pipeline reproducible locally','Blocked in review environment','Document the macOS OpenMP/libomp requirement and supported environment setup. Rerun the complete four-table pipeline from raw inputs. Clear the retained pip-install failure from the executed notebook by executing successfully.','A fresh environment following the setup instructions completes one-command processing and reproduces reported metrics, with a clean notebook run.','D1.3; reproducibility requirement')
task(15,'Write the executive readout','Missing','Create a 6-10 slide deck or executive memo for Operations and Finance. Lead with supported rupee exposure and recommended actions, then explain accuracy, assumptions and limitations plainly.','A non-technical reader can identify what to reorder, clear or investigate and the financial reasoning. This is D7 project content; uploading/submitting it is outside this checklist.','D7.1-D7.4')
add('Secondary items and boundaries','TaskX')
add('Appendix B describes MAPE as a secondary metric; it is not currently reported. If included, specify how zero-demand cases are handled. The explicit D3 acceptance metric is WAPE, which is already present.')
add('Optional stretch work is not counted as unfinished core scope: empirically calibrated intervals and a model-monitoring plan. Feature importance and an interactive service-level control already exist.')
add('<b>Review basis:</b> Zidio_Project_Data_1.1 (1).pdf, Sections 03-09 and 16, and Appendix B; local source, notebooks and saved outputs inspected on 30 September 2026. No project implementation was changed.','SmallX')
add('<b>Checks already performed:</b> the seeded dashboard and empty ABC selection ran without exceptions. No empty-results message appeared. Dependency installation succeeded, but pipeline startup failed at LightGBM import because libomp.dylib was absent. This is a setup limitation, not proof of a training-code failure.','SmallX')
add('<b>Team workflow:</b> assign an owner to each numbered item, complete data work first, then forecasting and risk, and finish dashboard integration and reports. Mark an item complete only after its "Done when" condition is demonstrated.','NoteX')

doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=38,bottomMargin=58,title='FORESIGHT - Pending Project Requirements',author='Project FORESIGHT review',subject='Non-deployment project completion checklist')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT.resolve())
