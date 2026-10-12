"""Declare an observed local target return without inventing public messages."""

from tempfile import TemporaryDirectory

from kuma import collect_public_messages, create_run


class LocalCase:
    """Supply one deterministic Input without requiring an Agent Profile."""

    agent_profile_required = False

    def generate_case(self, context):
        """Return the public task for this entirely local example."""
        return {"inputs": ["Add the integers 1, 2 and 3."]}


def target():
    """Execute the actual toy target and return its result, with no event stream."""
    return {"sum": sum((1, 2, 3))}


def main():
    """Retain an explicit producer locally; no model, network or Judge is used."""
    with TemporaryDirectory(prefix="kuma-output-actor-") as repository:
        run = create_run(
            repo_path=repository,
            case_provider=LocalCase(),
            max_steps=1,
            judge=False,
            track_files=False,
            save_local=True,
            allow_local=True,
        )
        run.get_input()
        observed_return = target()
        run.submit(
            observed_return,
            agent_output_actor="target_agent",
            public_messages=collect_public_messages([]),
        )
        submission = run.history[0].submission
        print(f"output_sum={submission.output['sum']}")
        print(f"output_actor={submission.extensions['agent_output_actor']}")
        print("public_messages=0; official_assessment=not_requested")


if __name__ == "__main__":
    main()
