## Issue (cloudtools/troposphere)

AWS Control Tower CloudFormation spec does not match docs
EnabledControl.EnabledControlParameter Value type according to docs is 'array, string, number, object, or boolean', but the spec simply states 'Json', which does not allow the values required.

https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-controltower-enabledcontrol-enabledcontrolparameter.html#cfn-controltower-enabledcontrol-enabledcontrolparameter-value

EnabledBaseline.Parameter Value type according to docs is String, but the spec here also states 'Json', which results in an invalid CloudFormation template.

https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-controltower-enabledbaseline-parameter.html#cfn-controltower-enabledbaseline-parameter-value

I haven't found how to tell AWS about this, but at least I know how to patch it in troposphere, so PR is incoming 😉

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
