// Package beval provides a behavioral evaluation framework for AI agents
// and LLM-powered systems.
//
// See SPEC.md §3 for core concepts. The package exposes a fluent DSL for
// defining evaluation cases, a grader registry, runner orchestration,
// subject normalization, and result reporting.
//
// Quick start:
//
//	s := beval.Case("AI legislation search", beval.Category("legislation"))
//	s.Given("a query", "What actions has Congress taken on AI policy?")
//	s.When("the agent researches this query")
//	s.Then("the answer should mention", "artificial intelligence")
package beval
