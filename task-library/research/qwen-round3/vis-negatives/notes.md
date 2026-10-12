# vis-001 Static Checker Negative Cases

Two targeted variants demonstrate risks in the current static frontend checker.

## Wrapping label

The variant wraps the email input in a label without a for attribute. This is a valid HTML label association, but the checker rejected it because it only recognizes label[for]. The check must support both explicit and wrapping labels.

## Declared palette with hard-coded low contrast

The variant keeps the declared palette unchanged but styles the hero supporting text with #DDDDDD on white, about 1.35:1 contrast. The static checker passed because it inspected the declared variable rather than the computed element color.

## Conclusion

Static source checks can identify structural signals and palette declarations, but cannot prove computed contrast or rendered behavior. Use a browser to inspect computed styles, responsive layout, and form states. Pair this with accessibility automation and human design review. Historical logs are under logs/.
