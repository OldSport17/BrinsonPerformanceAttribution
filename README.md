# BrinsonPerformanceAttribution
Data collection and Brinson Performance Attribution Model built with AI agents

## Background
•	As of April 2025, AI tools are perhaps more capable than we imagine. I hypothesized that the most advanced AI tools, complemented with investment domain expertise of a human, can materially improve analytical quality and productivity.
•	Based on that premise, I created a Brinson performance attribution model and data collection tool from scratch, solely based on my own knowledge and the help of various AI tools. 

## Goal
•	Create a Brinson attribution model and data collection framework from scratch using Python that enables performance attribution based on real life data and works without manual collection of data.
•	Create the model without the help of human experts, relying exclusively on publicly available information, data sources, and AI tools.

## Resources
•	AI tools: 
  o	Perplexity Pro: AI search engine that leverages most advanced AI models such as ChatGPT 4.1. Used for research on implementing Brinson models, availability of data, etc.
  o	Cursor Pro: AI-powered coding editor incorporating automatic code generation and embedded AI-agents that interacts with humans in natural language. Used as main code editor and platform to generate code from embedded AI agents.
  o	Embedded AI models used: ChatGPT 4.1, Gemini 2.5 Pro.
•	Data sources:
  o	Tradefeeds: Financial data API provider. Used for historical ETF holdings data and ETF identifier data.
  o	Yfinance: Popular Python library based on Yahoo Finance. Used for stock prices, sector, and industry data for performance attribution.
•	Internet 
  o	Google: Basic information search.
  o	Harborcapital.com: Information on Harbor Capital products.
  o	GitHub: Reference for existing codes and models.
  o	Morningstar: Search for ETF information and comparables.
  o	Yahoo Finance: Manual reference to validate model-generated outputs.

## Product Selection for Analysis
•	Target product - WINN
  o	Rationale: Active ETF with sufficient historical data, domestic product without currency impact.
•	Benchmark
  o	Original idea: IWF as proxy of Russell 1000 Growth Index.
  o	Selection: ILCG (iShares Morningstar Growth ETF). One of the comparable products listed in Morningstar. Covers large and mid-cap growth stocks. Passive alternative to WINN with similar performance. No date mismatch issue (see below).
•	Date mismatch issue
  o	WINN has fiscal year end of October 31st, making holdings data only available in sources I can access (i.e., no access to FactSet) to be end of Jan/Apr/Jul/Oct.
  o	ILCG has the same data date availability.
  o	Obtaining monthly data outside of the fiscal YE cycle requires professional-level data sources.

## Model Architecture
•	Data collection
  o	Tradefeeds: Using ETF ticker as key, fetches historical ETF holdings data. Using stock ISIN as key, fetches ETF identifier data (ISIN and Ticker) as this is not included in the ETF holdings data.
  o	Yfinance: Using Ticker as key, fetches sector and industry data, and ETF price and dividend data for total return calculation.
  o	All collected data is aggregated in DataFrames, and a single csv file is generated to be used for performance attribution.
•	Brinson Attribution Model
  o	Geometrically linked multi-period 1-factor (sector or industry) Brinson attribution model was created to handle multiple 3-month periods.
  o	Additional capability to generate a summary table showing sector/industry average weights and returns for reference.
•	Supplementary information/references
  o	Summary table showing weight/returns by ETFs
  o	Generate csv files for easy review of data
  o	Generate ETF price-based return data for the two ETFs for return output validation

## Implementation
•	Setting model architecture
  o	I constructed the intended model architecture as described above.
•	Code writing
  o	Generated initial code using natural language prompts on Perplexity and Cursor.
  o	Once the code is generated, I review the code to review the logical flow and clear errors.
  o	Run code: If code runs without issue, review output for sanity checks and data validation. If error occurs, identify error, understand the issue, consult the AI agent for a resolution, update, and rerun.
•	Debugging
  o	Significant errors in logic: Significant issues are identified by outlier/extreme outputs. Consulted AI agent explaining the language and implement possible resolutions. 
  o Example: Attribution output had very large allocation impact for Technology stocks. AI agent suggested possible issues, edited code to generate output to test each possible issue. I run the edited code and review possible outsized weight or period return figures, issues with normalization of weights (to add up to 100%), and linking multi-period returns. I found that the code logic compounds the period return across securities instead of over the few 3-month periods, resulting in very large numbers. This issue was resolved by corrected the code as proposed by the AI agent.
  o	Simple errors: Some minor errors were identified by me and corrected, with the validation of the AI agent.
  o Example: Incorrect capitalization of a parameter identified and corrected by me.
•	Data validation
  o	Sanity check: Review output data for outliers.
  o	Returns: Compare ETF return calculated based on ETF prices and holdings-based return data. 
  o	Sector holdings: Compare code output with ETF literature on Harborcapital.com
  o	Time period: Run attribution for different time periods to confirm code runs without issue.
  o	Generate summary table to review sector/industry weights within ETF and compared to benchmark ETF.
  o	Example in Appendix: Validating the difference between ETF return as calculated in holdings-based Brinson attribution logic and ETF total return based on price return and dividends. 

## Learnings and Implications
•	The most advanced AI tools have full capability to generate code based on natural language instructions coming from a domain expert without coding capabilities. With a basic level of coding knowledge, it is possible to interact with an AI coding agent to generate code that implement complicated logic/models such as a performance attribution model.
•	My main difficulty was in collecting data without access to professional-level tools such as FactSet. I spent a significant amount of time to create the data collection module that works without issue, which can be replaced by a simple query from FactSet/Bloomberg/Morningstar Direct.
•	Understanding both investments and coding is difficult. Each skill leverages very different aspects of your brain, and performing at a high-level for both is a very difficult act. For example, the ability to identify and conceptualize the most useful performance attribution approach for a given manager requires intuition, deep understanding of the manager's investment approach, and knowledge of the range of quantitative analysis that is possible given data availability. On the other hand, being a software engineer to implement that idea requires advance coding skills, and an absolute attention to detail (e.g., a missing comma will cause a big issue). AI tools are already powerful enough to help with both skills, particularly in translating ideas into code.
•	Seeing the result of AI-generated code is an indirect way to learn how to code in Python. It helps understand the logic and what information should be included in the code. This exercise inspired me to go deeper in learning Python. Combined with the AI tools, it will turbocharge my capability to create useful tools myself.
