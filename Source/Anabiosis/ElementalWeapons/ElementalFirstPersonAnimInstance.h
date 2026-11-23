#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "ElementalFirstPersonAnimInstance.generated.h"

/** Native graph: body locomotion -> arm pose/slot -> two hand IK. */
UCLASS(Transient)
class ANABIOSIS_API UElementalFirstPersonAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;
};
