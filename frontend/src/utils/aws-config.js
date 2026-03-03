// AWS configuration values from CDK deploy output.
// These are public Cognito and API Gateway identifiers, not secrets (see SEC-5).
const awsConfig = {
  Auth: {
    Cognito: {
      userPoolId: "us-east-1_suz5riOk5",
      userPoolClientId: "6a8c3m92724vrj80kbgpe47gjd",
      loginWith: { email: true },
    },
  },
  API: {
    REST: {
      EmailAnnotatorAPI: {
        endpoint: "https://1nhy7n8lld.execute-api.us-east-1.amazonaws.com/prod",
        region: "us-east-1",
      },
    },
  },
  Storage: {
    S3: {
      bucket: "emailannotatorstack-annotatorbucket45bbae1a-ihmajdqplmoc",
      region: "us-east-1",
    },
  },
};

export default awsConfig;
