"""GraphQL schema and resolvers. Types follow contracts/graphql/schema.graphql (ADR-002)."""

TYPE_DEFS = """
type TestCase {
  id: ID!
  name: String!
  category: String!
  version: String!
}

type TestResult {
  id: ID!
  runId: ID!
  passed: Boolean!
  details: String!
}

type Score {
  dimension: String!
  value: Float!
}

type Query {
  tests: [TestCase!]!
  runs: [TestRun!]!
  scores(target: String!): [Score!]!
}

type Mutation {
  registerTest(name: String!, category: String!): TestCase!
  startRun(target: String!, suite: [String!]!): TestRun!
}

"""

resolvers = {
    "Query": {},
    "Mutation": {},
}
